# Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.
# This file is licensed under The 3-Clause BSD License, with full text available at the end of the file.
# Contributors: Mx Onym, Sherry Ignatchenko


import heapq
import logging
import time
import traceback
from multiprocessing import Queue as PQueue, SimpleQueue, Process, shared_memory
from threading import Thread  # only for logging!

from summonmm.install.install_logging import add_logging_handler, set_logging_hook
from summonmm.tasks._tasks_common import *
from summonmm.tasks._tasks_logging import (
    LogQueue,
    OutLogQueue,
    ChildProcessLogHandler,
    create_logging_thread,
    log_waited,
    log_elapsed,
    EndOfRegularLog,
    StopSkipping,
)
from summonmm.tasks._tasks_shared import (
    _pool_of_shared_returns,  # pyright: ignore (it is better to keep _pool_of_shared_returns private)
    SharedReturnParam,
)


def _run_task(task: Task, depparams: list[Any]) -> tuple[Exception | None, Any]:
    ndep = len(depparams)
    assert ndep <= 3
    assert task.f is not None
    try:
        out: Any
        match ndep:
            case 0:
                out = task.f(task.param)  # type: ignore (if there is wrong number of params, we'll fail anyway)
            case 1:
                out = task.f(task.param, depparams[0])  # type: ignore
            case 2:
                out = task.f(task.param, depparams[0], depparams[1])  # type: ignore
            case 3:
                out = task.f(task.param, depparams[0], depparams[1], depparams[2])  # type: ignore
            case _:
                assert False
        return None, out
    except Exception as e:
        critical("Parallel: exception in task {}: {}".format(task.name, e))
        warn(traceback.format_exc())
        return e, None


type _QMsgTasks = list[Any]  # first one being Task, the rest are optional params
type InQueue = PQueue[tuple[_QMsgTasks | None, str | None] | None]
type _OutTask = tuple[str, tuple[float, float], Any]
type _OutQItem = Exception | ProcessStarted | tuple[int, list[_OutTask]]
type OutQueue = PQueue[_OutQItem]


def _process_nonown_tasks(
    tasks: _QMsgTasks, dwait: float | None
) -> tuple[Exception | None, list[_OutTask] | None]:
    assert isinstance(tasks, list)
    outtasks: list[_OutTask] = []
    for tplus in tasks:
        task = tplus[0]
        ndep = len(task.dependencies)
        assert len(tplus) == 1 + ndep
        t0 = time.perf_counter()
        tp0 = time.process_time()
        if dwait is not None:
            debug(
                "after waiting for {:.2f}s, starting task {}".format(dwait, task.name)
            )
            dwait = None
        else:
            debug("starting task {}".format(task.name))
        (ex, out) = _run_task(task, tplus[1:])
        if ex is not None:
            return ex, None  # for tplus
        elapsed = time.perf_counter() - t0
        cpu = time.process_time() - tp0
        info("done task {}, cpu/elapsed={:.2f}/{:.2f}s".format(task.name, cpu, elapsed))
        outtasks.append((task.name, (cpu, elapsed), out))
        # end of for tplus
    return None, outtasks


def _proc_func(
    proc_num: int,
    globalinits: list[LambdaReplacement],
    inq: InQueue,
    outq: OutQueue,
    logq: LogQueue,
) -> None:
    try:
        assert current_proc_num() == -1
        set_current_proc_num(proc_num)

        add_logging_handler(ChildProcessLogHandler(logq))
        run_global_process_initializers(globalinits)

        debug("Process started")
        outq.put(ProcessStarted(proc_num))
        ex = None
        while True:
            waitt0 = time.perf_counter()
            msg = inq.get()
            if msg is None:
                break  # while True

            dwait = time.perf_counter() - waitt0

            (tasks, processedshm) = msg
            if processedshm is not None:
                assert tasks is None
                info(
                    "after waiting for {:.2f}s, releasing shm={}".format(
                        dwait, processedshm
                    )
                )
                _pool_of_shared_returns.done_with(processedshm)
                continue  # while True

            assert tasks is not None
            ex, outtasks = _process_nonown_tasks(tasks, dwait)
            if ex is not None:
                break  # while True
            assert outtasks is not None
            outq.put((proc_num, outtasks))
            # end of while True

        if ex is not None:
            outq.put(ex)
    except Exception as e:
        # print('Exception!:'+traceback.format_exc())
        critical("_proc_func() internal exception: {}".format(repr(e)))
        warn(traceback.format_exc())
        outq.put(e)
    _pool_of_shared_returns.cleanup()
    debug("exiting process")


class _TaskGraphNodeState(IntEnum):
    Pending = 0
    Ready = 1
    Running = 2
    Done = 3


class _TaskGraphNode:
    task: Task
    children: list["_TaskGraphNode"]
    parents: "list[_TaskGraphNode]|list[str]"
    own_weight: float
    max_leaf_weight: float
    explicit_weight: bool
    state: _TaskGraphNodeState
    waiting_for_n_deps: int
    guaranteed_tags: list[str]

    def __init__(
        self,
        task: Task,
        parents: list["_TaskGraphNode"],
        weight: float,
        explicit_weight: bool,
        guaranteedtags: list[str],
    ) -> None:
        self.task = task
        self.children = []
        self.parents = parents
        self.own_weight = weight  # expected time in seconds
        self.max_leaf_weight = 0.0
        self.explicit_weight = explicit_weight
        self.state = _TaskGraphNodeState.Pending
        self.waiting_for_n_deps = 0
        self.guaranteed_tags = guaranteedtags

    def mark_as_done_and_handle_children(self) -> list["_TaskGraphNode"]:
        assert (
            self.state == _TaskGraphNodeState.Ready
            or self.state == _TaskGraphNodeState.Running
        )
        self.state = _TaskGraphNodeState.Done
        out: list["_TaskGraphNode"] = []
        for ch in self.children:
            assert ch.state == _TaskGraphNodeState.Pending
            assert ch.waiting_for_n_deps > 0
            ch.waiting_for_n_deps -= 1
            if ch.waiting_for_n_deps == 0:
                out.append(ch)
            else:
                debug(
                    "Parallel: task {} has {} remaining dependencies to become ready".format(
                        ch.task.name, ch.waiting_for_n_deps
                    )
                )

        return out

    def append_leaf(self, leaf: "_TaskGraphNode") -> None:
        self.children.append(leaf)
        self._adjust_leaf_weight(leaf.own_weight)

    def _adjust_leaf_weight(self, w: float) -> None:
        if self.max_leaf_weight < w:
            self.max_leaf_weight = w
            for p in self.parents:
                if isinstance(p, str) or int(p.state) >= int(_TaskGraphNodeState.Ready):
                    continue
                p._adjust_leaf_weight(self.own_weight + self.max_leaf_weight)

    def total_weight(self) -> float:
        return self.own_weight + self.max_leaf_weight

    # comparisons for heapq to work
    def __lt__(self, b: "_TaskGraphNode") -> bool:
        return self.total_weight() < b.total_weight()

    def __eq__(self, b: object) -> bool:
        assert isinstance(b, "_TaskGraphNode")
        return self.total_weight() == b.total_weight()


class _MainLoopTimer:
    stats: dict[str, float]  # stage name->time
    started: float
    cur_stage: str
    cur_stage_start: float
    ended: float | None

    def __init__(self, stage: str):
        self.stats = {}
        self.cur_stage = stage
        self.started = self.cur_stage_start = time.perf_counter()
        self.ended = None

    def stage(self, new_stage: str) -> float:
        t = time.perf_counter()
        dt = t - self.cur_stage_start
        if self.cur_stage not in self.stats:
            self.stats[self.cur_stage] = dt
        else:
            self.stats[self.cur_stage] += dt
        self.cur_stage = new_stage
        self.cur_stage_start = t
        return dt

    def end(self) -> None:
        t = time.perf_counter()
        if self.cur_stage not in self.stats:
            self.stats[self.cur_stage] = t - self.cur_stage_start
        else:
            self.stats[self.cur_stage] += t - self.cur_stage_start
        self.ended = t

    def log_timer_stats(self) -> None:
        assert self.ended is not None
        elapsed = self.ended - self.started
        info("Parallel/main process: elapsed {:.2f}s, including:".format(elapsed))
        total = 0.0
        for name, t in sorted(self.stats.items(), key=lambda x: -x[1]):
            info("-> {}: {:.2f}s".format(name, t))
            total += t
        if elapsed - total > 0.01:
            info("-> _unaccounted: {:.2f}s".format(elapsed - total))

    def elapsed(self) -> float:
        assert self.ended is not None
        return self.ended - self.started


type _StatsData = dict[str, tuple[int, float, float]]


class Parallel:
    _outq: OutQueue
    _logq: LogQueue
    _out_logq: OutLogQueue
    _processes: list[Process]
    _process_requests: list[list[float]]
    _inqueues: list[InQueue]
    _procrunningconfirmed: list[
        bool
    ]  # otherwise join() on a not running yet process may hang
    _logthread: Thread

    _nprocesses: int
    _json_fname: str | None
    _json_weights: dict[str, float]
    _updated_json_weights: dict[str, float]

    _shutting_down: bool
    _has_joined: bool

    publications: dict[
        str, shared_memory.SharedMemory
    ]  # semi-public: used by SharedPublication
    _all_task_nodes: dict[str, _TaskGraphNode]  # name->node
    _pending_task_nodes: dict[str, _TaskGraphNode]  # name->node
    _ready_task_nodes: dict[str, _TaskGraphNode]  # name->node
    _ready_task_nodes_heap: list[_TaskGraphNode]
    _ready_own_task_nodes: dict[str, _TaskGraphNode]  # name->node
    _ready_own_task_nodes_heap: list[_TaskGraphNode]
    _running_task_nodes: dict[
        str, tuple[int, float, _TaskGraphNode]
    ]  # name->(procnum,started,node)
    _done_task_nodes: dict[str, tuple[_TaskGraphNode, Any]]  # name->(node,out)
    _pending_patterns: list[tuple[str, _TaskGraphNode]]  # pattern, node
    _dbg_serialize: bool
    _old_logging_hook: Callable[[logging.LogRecord], None] | None | bool
    _task_stats_srch: FastSearchOverPartialStrings
    _task_stats_data: _StatsData
    _own_task_stats_data: _StatsData
    _task_stats_unaccounted: tuple[int, float, float]
    _own_task_stats_unaccounted: tuple[int, float, float]
    _data_dependencies: dict[str, int]
    _current_task_node: _TaskGraphNode | None
    _last_log_stats_str: str | None

    def __init__(
        self,
        jsonfname: str | None,
        nproc: int = 0,
        dbg_serialize: bool = False,
        taskstatsofinterest: TaskStatsOfInterest | None = None,
    ) -> None:
        # dbg_serialize allows debugging non-own Tasks
        assert current_proc_num() == -1

        assert nproc >= 0
        if nproc:
            self._nprocesses = nproc
        else:
            oscpu = os.cpu_count()
            assert oscpu is not None
            self._nprocesses = oscpu - 1  # -1 for the master process
        assert self._nprocesses >= 0
        self._dbg_serialize = dbg_serialize
        info("Parallel: using {} processes...".format(self._nprocesses))
        self._json_fname = jsonfname
        self._json_weights = {}
        self._updated_json_weights = {}
        if jsonfname is not None:
            try:
                with open(jsonfname, "rt", encoding="utf-8") as rf:
                    self._json_weights = json.load(rf)
            except Exception as e:
                warn(
                    "error loading JSON weights from {}: {}. Will continue w/o weights".format(
                        jsonfname, e
                    )
                )
                self._json_weights = {}  # just in case

        self._shutting_down = False
        self._has_joined = False

        self.publications = {}

        self._all_task_nodes = {}
        self._pending_task_nodes = {}
        self._ready_task_nodes = {}
        self._ready_task_nodes_heap = []
        self._ready_own_task_nodes = {}
        self._ready_own_task_nodes_heap = []
        self._running_task_nodes = {}  # name->(procnum,started,node)
        self._done_task_nodes = {}  # name->(node,out)
        self._pending_patterns = []

        if taskstatsofinterest is None:
            taskstatsofinterest = []
        self._task_stats_srch = FastSearchOverPartialStrings(
            [(prefix, 1) for prefix in taskstatsofinterest]
        )
        self._task_stats_data = {}
        self._own_task_stats_data = {}
        self._task_stats_unaccounted = (0, 0.0, 0.0)
        self._own_task_stats_unaccounted = (0, 0.0, 0.0)
        self._old_logging_hook = False
        self._data_dependencies = {}
        self._current_task_node = None
        self._last_log_stats_str = None

    def __enter__(self) -> "Parallel":
        increment_parallel_count()
        self._old_logging_hook = set_logging_hook(
            lambda rec: self._logq.put((-1, time.perf_counter(), rec))
        )
        self._processes = []
        self._process_requests = []
        # but not as keeping simplistic processesload[i] == 2 (it disbalances end of processing way too much)
        self._inqueues = []
        self._procrunningconfirmed = (
            []
        )  # otherwise join() on a not running yet process may hang
        self._outq = PQueue()
        self._logq = SimpleQueue()
        self._out_logq = SimpleQueue()
        self._logthread = create_logging_thread(self._logq, self._out_logq)
        self._logthread.start()
        for i in range(self._nprocesses):
            inq: InQueue = PQueue()
            self._inqueues.append(inq)
            p = Process(
                target=_proc_func,
                args=(
                    i,
                    get_global_process_initializers(),
                    inq,
                    self._outq,
                    self._logq,
                ),
            )
            self._processes.append(p)
            p.start()
            self._process_requests.append([])
            self._procrunningconfirmed.append(False)
        self._shutting_down = False
        self._has_joined = False
        assert len(self._process_requests) == len(self._processes)
        assert len(self._inqueues) == len(self._processes)
        return self

    def _dependencies_to_parents(
        self, dependencies: list[str]
    ) -> tuple[list[_TaskGraphNode] | None, list[str] | None]:
        taskparents: list[_TaskGraphNode] = []
        patterns: list[str] = []
        for d in dependencies:
            if d.endswith("*"):
                patterns.append(d[:-1])
                continue
            pnode = self._all_task_nodes.get(d)
            if pnode is None:
                return None, None
            else:
                taskparents.append(pnode)
        return taskparents, patterns

    def _internal_add_task_if(self, task: Task) -> bool:
        assert isinstance(task, OwnTask) or task.data_dependencies is None

        assert current_proc_num() == -1

        assert task.name not in self._all_task_nodes
        assert (
            isinstance(task, OwnTask)
            or isinstance(task, TaskPlaceholder)
            or task.f is not None
            and not is_lambda(task.f)
        )

        taskparents, patterns = self._dependencies_to_parents(task.dependencies)
        if taskparents is None:
            assert patterns is None
            return False
        assert patterns is not None
        if __debug__:
            for p in taskparents:
                assert isinstance(p, _TaskGraphNode)

        # by this point, we're sure that we'll add this particular task
        # checking data tags
        guaranteedtags: set[str] = set()
        if self._current_task_node is not None:
            for gt in self._current_task_node.guaranteed_tags:
                guaranteedtags.add(gt)
        for n in taskparents:
            for gt in n.guaranteed_tags:
                guaranteedtags.add(gt)
        if task.data_dependencies is not None:
            for d in task.data_dependencies.required_tags:
                if d not in guaranteedtags:
                    critical(
                        "Parallel: missing datadep={} for task {}".format(d, task.name)
                    )
                    assert False
            for nd in task.data_dependencies.required_not_tags:
                if nd in guaranteedtags:
                    critical(
                        "Parallel: prohibited datadep={} for task {}".format(
                            nd, task.name
                        )
                    )
                    assert False
            for pd in task.data_dependencies.provided_tags:
                guaranteedtags.add(pd)

        # adding task
        w = task.w
        explicitw = True
        if w is None:
            explicitw = False
            w = (
                0.1 if isinstance(task, OwnTask) else 1.0
            )  # 1 sec for non-owning tasks, and assuming that own tasks are shorter by default (they should be)
            w = self.estimated_time(task.name, w)
        node = _TaskGraphNode(task, taskparents, w, explicitw, list(guaranteedtags))
        assert task.name not in self._all_task_nodes
        self._all_task_nodes[task.name] = node

        assert node.waiting_for_n_deps == 0
        if isinstance(task, TaskPlaceholder):
            node.waiting_for_n_deps = (
                1000000  # 1 would do, but 1000000 is much better visible in debug
            )
        for parent in node.parents:
            assert isinstance(parent, _TaskGraphNode)
            parent.append_leaf(node)
            if int(parent.state) < int(_TaskGraphNodeState.Done):
                node.waiting_for_n_deps += 1

        # processing other task's dependencies on this task's patterns
        for p in patterns:
            for n in self._all_task_nodes.values():
                if n.state < _TaskGraphNodeState.Done and n.task.name.startswith(p):
                    node.waiting_for_n_deps += 1
                    n.children.append(node)
                    debug(
                        "Parallel: adding task {} with pattern {}, now it has {} dependencies due to existing task {}".format(
                            node.task.name, p, node.waiting_for_n_deps, n.task.name
                        )
                    )
            node.parents.append(p)  # type: ignore ; spurious - node.parents can be list[str] too
            self._pending_patterns.append((p, node))

        debug(
            "Parallel: added task {}, which is waiting for {} dependencies".format(
                node.task.name, node.waiting_for_n_deps
            )
        )

        assert node.state == _TaskGraphNodeState.Pending
        if node.waiting_for_n_deps == 0:
            node.state = _TaskGraphNodeState.Ready
            if isinstance(node.task, OwnTask):
                self._ready_own_task_nodes[task.name] = node
                heapq.heappush(self._ready_own_task_nodes_heap, node)
            else:
                self._ready_task_nodes[task.name] = node
                heapq.heappush(self._ready_task_nodes_heap, node)
        else:
            self._pending_task_nodes[task.name] = node

        # processing other task's pattern dependencies on this task
        for pp in self._pending_patterns:
            (p, n) = pp
            if task.name.startswith(p):
                node.children.append(n)
                n.waiting_for_n_deps += 1
                debug(
                    "Parallel: task {} now has {} dependencies due to added task {}".format(
                        n.task.name, n.waiting_for_n_deps, node.task.name
                    )
                )

        return True

    def add_tasks(self, tasks: list[Task]) -> None:
        while len(tasks) > 0:
            megaok = False
            for t in tasks:
                ok = self._internal_add_task_if(t)
                if ok:
                    tasks.remove(t)
                    megaok = True
                    break  # for t

            if megaok:
                continue  # while True
            else:
                taskstr = "[\n"
                for task in tasks:
                    taskstr += "    " + str(task.__dict__) + ",\n"
                taskstr += "\n]"

                critical(
                    "Parallel: probable typo in task name or circular dependency: cannot resolve tasks:\n"
                    + taskstr
                    + "\n"
                )
                raise_if_not(False)

    def _run_all_own_tasks(self, mltimer: _MainLoopTimer) -> bool:
        ran = False
        assert len(self._ready_own_task_nodes) == len(self._ready_own_task_nodes_heap)
        while len(self._ready_own_task_nodes) > 0:
            self._run_own_task(
                mltimer
            )  # ATTENTION: own tasks may call add_task() or add_tasks() within
            ran = True
        return ran

    @staticmethod
    def _log_stats_data(
        stats: _StatsData, unaccounted: tuple[int, float, float]
    ) -> None:
        for item in sorted(stats.items(), key=lambda t: -t[1][2]):
            if item[1][0] != 0:
                info(
                    "-> {}*: {}, took {:.2f}/{:.2f}s".format(
                        item[0], item[1][0], item[1][1], item[1][2]
                    )
                )
        if unaccounted[0]:
            warn(
                "-> _unaccounted: {}, took {:.2f}/{:.2f}s".format(
                    unaccounted[0], unaccounted[1], unaccounted[2]
                )
            )

    def run(self, tasks: list[Task]) -> None:
        # building task graph
        self.add_tasks(tasks)

        # graph ok, running the initial tasks
        assert len(self._pending_task_nodes)
        mltimer = _MainLoopTimer("overhead")
        maintexttasks = 0.0

        # we need to try running own tasks before main loop - otherwise we can get stuck in an endless loop of self._schedule_best_tasks()
        mltimer.stage("own-tasks.overhead")
        self._run_all_own_tasks(mltimer)
        mltimer.stage("overhead")

        # main loop
        while True:
            # place items in process queues, until each has 2 tasks, or until there are no tasks
            mltimer.stage("scheduler")
            while True:
                ok, dt = self._schedule_best_tasks(mltimer)
                maintexttasks += dt
                if not ok:
                    break

            mltimer.stage("own-tasks.overhead")
            ran = self._run_all_own_tasks(mltimer)

            if ran:
                mltimer.stage("scheduler")
                while True:
                    ok, dt = self._schedule_best_tasks(mltimer)
                    maintexttasks += dt
                    if not ok:
                        break

            if __debug__:
                mltimer.stage("logging-stats")
                self._log_stats(dbglevel=logging.DEBUG)

            mltimer.stage("scheduler")
            done = self.is_all_done()
            if done:
                break

            # waiting for other processes to report
            mltimer.stage("waiting")
            got = self._outq.get()
            dwait = mltimer.stage("overhead")
            if __debug__:  # pickle.dumps is expensive by itself
                debug("Parallel: response size: {}".format(len(pickle.dumps(got))))
            # warn(str(self.logq.qsize()))
            if isinstance(got, Exception):
                critical(
                    "Parallel: An exception within child process reported. Shutting down"
                )

                if not self._shutting_down:
                    self.shutdown(True)
                info("Parallel: shutdown ok")
                if not self._has_joined:
                    self.join_all(True)

                critical(
                    "Parallel: All children terminated, aborting due to an exception in a child process. For the exception itself, see log above."
                )
                # noinspection PyProtectedMember, PyUnresolvedReferences
                os._exit(1)  # if using sys.exit(), confusing logging will occur

            if isinstance(got, ProcessStarted):
                self._procrunningconfirmed[got.proc_num] = True
                continue  # while True

            strwait = "{:.2f}s".format(dwait)
            msgwarn = False
            if dwait < 0.005:
                strwait += "[MAIN THREAD SERIALIZATION]"
                msgwarn = True

            (procnum, outtasks) = got

            info_or_perf_warn(
                msgwarn,
                "Parallel: after waiting for {}, received results of {} task(s) from process #{}".format(
                    strwait, len(tasks), procnum + 1
                ),
            )

            assert len(self._process_requests[procnum]) > 0
            self._process_requests[procnum] = self._process_requests[procnum][1:]

            maintexttasks += self._process_out_tasks(procnum, outtasks)

            mltimer.stage("logging-stats")
            self._log_stats(dbglevel=logging.INFO)

            mltimer.stage("scheduler")
            done = self.is_all_done()
            if done:
                break

        mltimer.end()
        self._logq.put(StopSkipping())

        elapsed = mltimer.elapsed()
        nonmainpct = maintexttasks / elapsed * 100.0
        info_or_perf_warn(
            nonmainpct < 100.0,
            "Parallel: child processes load {:.2f}s ({:.1f}% of one core, {:.1f}% of {} cores)".format(
                maintexttasks,
                nonmainpct,
                nonmainpct / self._nprocesses,
                self._nprocesses,
            ),
        )
        info("Parallel: breakdown per child task type of interest:")
        Parallel._log_stats_data(self._task_stats_data, self._task_stats_unaccounted)
        mltimer.log_timer_stats()
        waiting = mltimer.stats["waiting"]
        mainpct = (elapsed - waiting) / elapsed * 100.0
        info_or_perf_warn(
            mainpct > 50.0, "Parallel: main process load {:.1f}%".format(mainpct)
        )

        info("Parallel: breakdown per own task type of interest:")
        Parallel._log_stats_data(
            self._own_task_stats_data, self._own_task_stats_unaccounted
        )

    def _node_is_ready(self, ch: _TaskGraphNode) -> None:
        assert ch.state == _TaskGraphNodeState.Pending
        assert ch.task.name not in self._ready_task_nodes
        assert ch.task.name not in self._ready_own_task_nodes
        assert ch.task.name in self._pending_task_nodes
        debug("Parallel: task {} is ready".format(ch.task.name))
        ch.state = _TaskGraphNodeState.Ready
        del self._pending_task_nodes[ch.task.name]
        if isinstance(ch.task, OwnTask):
            self._ready_own_task_nodes[ch.task.name] = ch
            heapq.heappush(self._ready_own_task_nodes_heap, ch)
        else:
            self._ready_task_nodes[ch.task.name] = ch
            heapq.heappush(self._ready_task_nodes_heap, ch)

    def _process_out_tasks(self, procnum: int, tasks: list[_OutTask]) -> float:
        outt = 0.0
        for taskname, times, out in tasks:
            assert taskname in self._running_task_nodes
            (expectedprocnum, started, node) = self._running_task_nodes[taskname]
            assert node.state == _TaskGraphNodeState.Running
            (cput, taskt) = times
            assert procnum == expectedprocnum
            dt = time.perf_counter() - started
            debug(
                "Parallel: task {} from process #{} took elapsed/task/cpu={:.2f}/{:.2f}/{:.2f}s".format(
                    taskname, procnum + 1, dt, taskt, cput
                )
            )
            self._update_task_stats(False, taskname, cpu=cput, elapsed=taskt)
            outt += taskt

            self._update_weight(taskname, taskt)
            del self._running_task_nodes[taskname]
            assert taskname not in self._done_task_nodes
            rdy = node.mark_as_done_and_handle_children()
            for ch in rdy:
                self._node_is_ready(ch)
            self._done_task_nodes[taskname] = (node, out)

        return outt

    def _schedule_best_tasks(
        self, mltimer: _MainLoopTimer
    ) -> tuple[bool, float]:  # may schedule multiple tasks as one meta-task
        assert len(self._ready_task_nodes) == len(self._ready_task_nodes_heap)
        if len(self._ready_task_nodes) == 0:
            return False, 0.0

        pidx = self._find_best_process() if not self._dbg_serialize else 0
        if pidx < 0:
            return False, 0.0
        taskpluses: list[list[Any]] = []
        total_time = 0.0
        tasksstr = "["
        t0 = time.perf_counter()
        i = 0
        tout = 0.0
        while (
            len(self._ready_task_nodes) > 0 and total_time < 0.1
        ):  # heuristics: <0.1s is not worth jerking around
            assert len(self._ready_task_nodes) == len(self._ready_task_nodes_heap)
            node = heapq.heappop(self._ready_task_nodes_heap)
            assert not isinstance(node.task, OwnTask) and not isinstance(
                node.task, TaskPlaceholder
            )
            i += 1
            taskplus: list[Any] = [node.task]
            assert len(node.task.dependencies) == len(node.parents)
            for parent in node.parents:
                if isinstance(parent, _TaskGraphNode):
                    done = self._done_task_nodes[parent.task.name]
                    taskplus.append(done[1])
                else:
                    assert isinstance(parent, str)
            assert len(taskplus) == 1 + len(node.task.dependencies)

            assert node.state == _TaskGraphNodeState.Ready
            assert node.task.name in self._ready_task_nodes
            del self._ready_task_nodes[node.task.name]
            node.state = _TaskGraphNodeState.Running
            self._running_task_nodes[node.task.name] = (pidx, t0, node)

            taskpluses.append(taskplus)
            total_time += node.own_weight
            tasksstr += ",+" + node.task.name

        tasksstr += "]"
        if len(taskpluses) == 0:
            return False, 0.0

        if self._dbg_serialize:
            ex, out = _process_nonown_tasks(taskpluses, None)
            if ex is not None:
                raise ex
            assert out is not None
            tout += self._process_out_tasks(pidx, out)
            return True, tout

        self._process_requests[pidx].append(total_time)

        msg = (taskpluses, None)
        mltimer.stage("scheduler.queue-put")
        self._inqueues[pidx].put(msg)
        mltimer.stage("scheduler")
        # self.logq.put((-1,time.perf_counter(),make_log_record(logging.INFO, 'Parallel: assigned tasks {} to process #{}'.format(tasksstr, pidx + 1))))
        mltimer.stage("scheduler.logging")
        info("Parallel: assigned tasks {} to process #{}".format(tasksstr, pidx + 1))
        if __debug__:  # pickle.dumps is expensive by itself
            debug("Parallel: request size: {}".format(len(pickle.dumps(msg))))
        mltimer.stage("scheduler")
        return True, tout

    def _notify_sender_shm_done(self, pidx: int, name: str) -> None:
        if pidx < 0:
            assert pidx == -1
            debug("Parallel: Releasing own shm={}".format(name))
            _pool_of_shared_returns.done_with(name)
        else:
            self._inqueues[pidx].put((None, name))

    @staticmethod
    def _update_task_stats_internal(
        some_task_stats_data: _StatsData,
        srch: tuple[str, tuple[int, float, float]],
        cpu: float,
        elapsed: float,
    ) -> None:
        (key, _) = srch
        found = some_task_stats_data.get(key)
        if found is None:
            some_task_stats_data[key] = (1, cpu, elapsed)
        else:
            some_task_stats_data[key] = (
                found[0] + 1,
                found[1] + cpu,
                found[2] + elapsed,
            )

    def _update_task_stats(
        self, isown: bool, name: str, cpu: float, elapsed: float
    ) -> None:
        srch = self._task_stats_srch.find_val_for_str(name)

        if isown:
            if srch is None:
                self._own_task_stats_unaccounted = (
                    self._own_task_stats_unaccounted[0] + 1,
                    self._own_task_stats_unaccounted[1] + cpu,
                    self._own_task_stats_unaccounted[2] + elapsed,
                )
                return
            Parallel._update_task_stats_internal(
                self._own_task_stats_data, srch, cpu, elapsed
            )
        else:
            if srch is None:
                self._task_stats_unaccounted = (
                    self._task_stats_unaccounted[0] + 1,
                    self._task_stats_unaccounted[1] + cpu,
                    self._task_stats_unaccounted[2] + elapsed,
                )
                return
            Parallel._update_task_stats_internal(
                self._task_stats_data, srch, cpu, elapsed
            )

    def _run_own_task(self, mltimer: _MainLoopTimer) -> None:
        assert self._current_task_node is None
        assert len(self._ready_own_task_nodes) > 0
        towntask = 0.0
        mltimer.stage("scheduler")
        ot = heapq.heappop(self._ready_own_task_nodes_heap)
        mltimer.stage("own-tasks.overhead")

        assert isinstance(ot.task, OwnTask)
        # debug('own task: '+ot.task.name)
        if __debug__ and ot.task.data_dependencies is not None:
            dd = ot.task.data_dependencies
            for req in dd.required_tags:
                assert req in self._data_dependencies
            for reqnot in dd.required_not_tags:
                assert reqnot not in self._data_dependencies
            for prov in dd.provided_tags:
                self._data_dependencies[prov] = 1

        params: list[Any] = []
        assert len(ot.parents) == len(ot.task.dependencies)
        for p in ot.parents:
            if isinstance(p, _TaskGraphNode):
                param = self._done_task_nodes[p.task.name]
                params.append(param[1])
            else:
                assert isinstance(p, str)

        assert len(params) <= len(ot.task.dependencies)
        assert len(params) <= 3

        mltimer.stage("own-tasks.logging")
        debug("Parallel: running own task {}".format(ot.task.name))
        t0 = time.perf_counter()
        tp0 = time.process_time()

        mltimer.stage("own-tasks")
        # nall = len(self.all_task_nodes)
        # ATTENTION: ot.task.f(...) may call add_task() or add_task(s) within
        assert self._current_task_node is None
        self._current_task_node = ot
        (ex, out) = _run_task(ot.task, params)
        self._current_task_node = None
        if ex is not None:
            raise Exception("Parallel: Exception in user OwnTask.run(), quitting")
        # newnall = len(self.all_task_nodes)
        # assert newnall >= nall
        # wereadded = newnall > nall

        elapsed = time.perf_counter() - t0
        cpu = time.process_time() - tp0
        mltimer.stage("own-tasks.logging")
        debug(
            "Parallel: done own task {}, cpu/elapsed={:.2f}/{:.2f}s".format(
                ot.task.name, cpu, elapsed
            )
        )
        towntask += elapsed

        mltimer.stage("scheduler")
        self._update_task_stats(True, ot.task.name, cpu, elapsed)
        self._update_weight(ot.task.name, elapsed)

        assert ot.state == _TaskGraphNodeState.Ready
        assert ot.task.name in self._ready_own_task_nodes
        del self._ready_own_task_nodes[ot.task.name]
        rdy = ot.mark_as_done_and_handle_children()
        for ch in rdy:
            self._node_is_ready(ch)
        ot.state = _TaskGraphNodeState.Done
        self._done_task_nodes[ot.task.name] = (ot, out)
        mltimer.stage("own-tasks.overhead")

    def is_all_done(self) -> bool:
        return len(self._done_task_nodes) == len(self._all_task_nodes)

    def add_task(self, task: Task) -> None:  # to be called from owntask.f()
        assert task.name not in self._all_task_nodes
        added = self._internal_add_task_if(task)
        raise_if_not(
            added,
            lambda: "Parallel: cannot add task {}, are you sure all dependencies are known?".format(
                task.name
            ),
        )

    def replace_task_placeholder(self, task: Task) -> None:
        assert task.name in self._all_task_nodes
        assert task.name in self._pending_task_nodes
        oldtasknode = self._pending_task_nodes[task.name]
        assert oldtasknode.state == _TaskGraphNodeState.Pending
        assert isinstance(oldtasknode.task, TaskPlaceholder)
        children = self._pending_task_nodes[task.name].children
        del self._pending_task_nodes[task.name]
        del self._all_task_nodes[task.name]
        self.add_task(task)
        assert task.name in self._pending_task_nodes
        assert len(self._pending_task_nodes[task.name].children) == 0
        self._pending_task_nodes[task.name].children = children
        debug(
            "Parallel: replaced task placeholder {}, inherited {} children".format(
                task.name, len(children)
            )
        )

    def _find_best_process(self) -> int:
        best = -1
        bestf = None
        for i in range(len(self._process_requests)):
            if len(self._process_requests[i]) == 0:
                return i
            elif len(self._process_requests[i]) == 1:
                if bestf is None:
                    best = i
                    bestf = self._process_requests[i][0]
                elif self._process_requests[i][0] < bestf:
                    best = i
                    bestf = self._process_requests[i][0]

        return best

    def received_shared_return(self, sharedparam: SharedReturnParam) -> Any:
        (name, sender) = sharedparam
        shm = shared_memory.SharedMemory(name)
        out = pickle.loads(shm.buf)
        self._notify_sender_shm_done(sender, name)
        return out

    def _update_weight(self, taskname: str, dt: float) -> None:
        task = self._all_task_nodes[taskname].task
        if (
            task.w is None
        ):  # if not None - no sense in saving tasks with explicitly specified weights
            oldw = self._json_weights.get(taskname)
            if oldw is None:
                self._updated_json_weights[taskname] = dt
            else:
                self._updated_json_weights[taskname] = (
                    oldw + dt
                ) / 2  # heuristics to get some balance between new value and history
        else:
            if abs(task.w - dt) > task.w * 0.3:  # ~30% tolerance
                debug(
                    "Parallel: task {}: expected={:.2f}, real={:.2f}".format(
                        task.name, task.w, dt
                    )
                )

    def estimated_time(self, taskname: str, defaulttime: float) -> float:
        return self._updated_json_weights.get(
            taskname, self._json_weights.get(taskname, defaulttime)
        )

    def copy_estimates(self) -> dict[str, float]:
        return self._json_weights | self._updated_json_weights

    @staticmethod
    def estimated_time_from_estimates(
        estimates: dict[str, float], taskname: str, defaulttime: float
    ) -> float:
        return estimates.get(taskname, defaulttime)

    def all_estimates_for_prefix(
        self, tasknameprefix: str
    ) -> Generator[tuple[str, float]]:
        lprefix = len(tasknameprefix)
        for tn, t in self._updated_json_weights.items():
            if tn.startswith(tasknameprefix):
                yield tn[lprefix:], t
        for tn, t in self._json_weights.items():
            if tn.startswith(tasknameprefix):
                yield tn[lprefix:], t

    def shutdown(self, force: bool) -> None:
        assert not self._shutting_down

        if force:
            for i in range(self._nprocesses):
                self._processes[i].kill()
        else:
            for i in range(self._nprocesses):
                self._inqueues[i].put(None)
        # self.logq.put(None) - moved to join_all() to prevent processes hanging because of unread log messages
        # print('Parallel: shutting down')
        self._logq.put(EndOfRegularLog())
        self._shutting_down = True

    def join_all(self, force: bool) -> None:
        assert self._shutting_down
        assert not self._has_joined

        # read late log messages from logq; if we don't read them, processes may not terminate
        # while True:
        #   try:
        #        record = self.logq.get(False)
        #        (procnum, t, rec) = record
        #        assert isinstance(rec, logging.LogRecord)
        #        _patch_log_rec(rec, procnum, t)
        #        log_record(rec)
        #    except QueueEmpty:
        #        break

        # for i in range(len(self.inqueues)):
        #    j = 0
        #    while not self.inqueues[i].empty():
        #        self.inqueues[i].get()
        #        j += 1
        #    if j != 0:
        #        alert('{} unread messages from process #{}, skipped'.format(j,i+1))
        #

        if not force:
            n = 0
            while not all(self._procrunningconfirmed):
                if n == 0:
                    info(
                        "Parallel: joinAll(): waiting for all processes to confirm start before joining to avoid not started yet join race"
                    )
                    n = 1
                got = self._outq.get()
                if isinstance(got, ProcessStarted):
                    self._procrunningconfirmed[got.proc_num] = True
                    # debug('Parallel: joinAll(): process #{} confirmed as started',got.procnum+1)

        teol0 = time.perf_counter()
        endoflog = self._out_logq.get()
        assert endoflog is None
        dteol = time.perf_counter() - teol0
        if self._old_logging_hook is not False:
            assert not isinstance(self._old_logging_hook, bool)
            set_logging_hook(self._old_logging_hook)
            self._old_logging_hook = False
            # debug() should go after set_logging_hook()
            info_or_perf_warn(
                dteol > 0.05,
                "Parallel: after waiting for {:.2f}s for log thread to process its queue, setting logging hook back to {}".format(
                    dteol, repr(self._old_logging_hook)
                ),
            )
        else:
            info_or_perf_warn(
                dteol > 0.05,
                "Parallel: took {:.2f}s to wait for log thread to process its queue".format(
                    dteol
                ),
            )
        # print('synced with log thread')

        info("All processes confirmed as started, waiting for joins")
        for i in range(self._nprocesses):
            self._processes[i].join()
            debug("Process #{} joined".format(i + 1))

        self._logq.put(
            None
        )  # moved here to prevent processes hanging because of unread log messages
        self._logthread.join()
        self._has_joined = True

    def unpublish(self, name: str) -> None:
        pub = self.publications[name]
        pub.close()
        del self.publications[name]

    def _log_stats(self, dbglevel: int) -> None:
        assert len(self._ready_task_nodes) == len(self._ready_task_nodes_heap)
        statsstr = "Parallel: {} tasks, including {} pending, {}/{} ready, {} running, {} done".format(
            len(self._all_task_nodes),
            len(self._pending_task_nodes),
            len(self._ready_task_nodes),
            len(self._ready_own_task_nodes),
            len(self._running_task_nodes),
            len(self._done_task_nodes),
        )
        if statsstr != self._last_log_stats_str:
            log_with_level(dbglevel, statsstr)
            self._last_log_stats_str = statsstr

        if __debug__:
            debug(
                "Parallel: pending tasks (up to 10 first): {}".format(
                    repr([t for t in self._pending_task_nodes][:10])
                )
            )
            debug(
                "Parallel: ready tasks (up to 10 first): {}".format(
                    repr([t for t in self._ready_task_nodes][:10])
                )
            )
            debug(
                "Parallel: ready own tasks: {}".format(
                    repr([t for t in self._ready_own_task_nodes])
                )
            )
            debug(
                "Parallel: running tasks (up to 10 first): {}".format(
                    repr([t for t in self._running_task_nodes][:10])
                )
            )
        assert len(self._all_task_nodes) == len(self._pending_task_nodes) + len(
            self._ready_task_nodes
        ) + len(self._ready_own_task_nodes) + len(self._running_task_nodes) + len(
            self._done_task_nodes
        )

    def __exit__(
        self,
        exceptiontype: BaseException | None,
        exceptionval: BaseException | None,
        exceptiontraceback: TracebackType | None,
    ):
        decrement_parallel_count()
        force = False
        if exceptiontype is not None:
            critical(
                "Parallel: exception {}: {}".format(
                    str(exceptiontype), repr(exceptionval)
                )
            )
            alert("\n".join(traceback.format_tb(exceptiontraceback)))
            force = True

        if not self._shutting_down:
            self.shutdown(force)
        if not self._has_joined:
            self.join_all(force)

        lelapsed = log_elapsed()
        if lelapsed is not None:
            logpct = (lelapsed - log_waited()) / lelapsed * 100.0
            info_or_perf_warn(
                logpct > 50.0, "Parallel: logging thread load {:.1f}%".format(logpct)
            )
        else:
            warn("Parallel: logging thread did not finish properly?")

        names = [name for name in self.publications]
        for name in names:
            self.unpublish(name)

        if exceptiontype is None:
            if self._json_fname is not None:
                sortedw = dict(
                    sorted(
                        self._updated_json_weights.items(), key=lambda item: -item[1]
                    )
                )
                with open(self._json_fname, "wt", encoding="utf-8") as wf:
                    # noinspection PyTypeChecker
                    json.dump(sortedw, wf, indent=2)


"""
The 3-Clause BSD License

Copyright (C) 2024-2025 Six Impossible Things Before Breakfast Limited.

Contributors: Mx Onym, Sherry Ignatchenko

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
may be used to endorse or promote products derived from this software
without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
