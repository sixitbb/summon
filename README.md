# S.U.M.M.O.N. - A Next-Generation Mod Manager
As original author of the S.U.M.M.O.N. has learned the hard way, existing mod managers (yes, even Mod Organizer) have quite a few significant limitations. So they started this project, which eventually grew into a full-scale mod manager.

## WTF does S.U.M.M.O.N. stand for?
S.U.M.M.O.N. is your typical [backronym](https://en.wikipedia.org/wiki/Backronym), and currently stands for:

* S. - Semi-Automatic
* U. - Up-to-Date (also in Irish: [Uilefheasach](https://en.wiktionary.org/wiki/uilefheasach), which can be translated as [omniscient](https://en.wiktionary.org/wiki/omniscient))
* M. - Mod
* M. - Management
* O. - Over
* N. - the Network

Or, considering S.U.M.M.O.N. as a whole word: you can **SUMMON** an existing mod config (BTW, summoning will happen over the network, as it was written on the tin), which was carefully prepared by the others, *and use it as a starting point for your own modding journey*.

## Definiencies in Existing Mod Managers
1. As we're 95% sure, existing mod managers (including MO2) do not always keep mod folders pristine after install, at least not *forever*. In particular, if a tool such as BodySlide modifies a file which *already exists* in the mod folder - the file will be modified within mod folder, *even when tool is running from under MO2*, which goes against the main idea of the mods being fully separated. 
  * *NB: it is NEW files which will go into `overwrite`; EXISTING files will be modified wherever they already are*
  * S.U.M.M.O.N. can detect such modifications, and "heal" them, fixing the problem, AND preventing it from re-appearing in the future. Moreover, most of the time S.U.M.M.O.N. can do it on an existing mod config, *months and even years after it has happened*. <sup>(*)</sup> 
2. Existing Mod Managers (incl. MO2) are "all or nothing"; you cannot start using them gradually, neither you can migrate your existing mod setup from "flat" structure (placing mods directly into game folder) to mod manager VFS *automatically*. 
  * In contrast, S.U.M.M.O.N. can live *alongside* an existing MO2 setup (plugin to support Vortex is pending); heck, in the medium-run we should be able even to perform a mostly-automated migration from "flat" setup right in the game folder, to the mod manager VFS-driven data structure <sup>(*)</sup> 

BTW, we're certainly NOT trying to diminish importance of Mod Organizer and MO2 - it **was** THE thing which has changed modding  *forever*. However, as it is *possible* to do better than MO2 - it is **necessary** to do it better than MO2. And that's what we're trying to do with S.U.M.M.O.N. 

## MAJOR New Features in S.U.M.M.O.N.
1. Support for creation of *automated* install guides (hi, S.T.E.P. folks)
  * We admire all the hard work of S.T.E.P. (from [stepmodifications.org](https://stepmodifications.org/)) and other modding guides. However, with all due respect, their estimates of the time needed to install them, are *hugely* underestimated. At least the original author of the S.U.M.M.O.N. has never been able to install S.T.E.P. in less than a *week* - and that's IF they didn't make a mistake. 
  * OTOH, 90+% of the installation instructions in S.T.E.P. are actually *very formal* - as in "install this archive using such and such FOMOD options, and then move these two .esp files to /optional/ folder". S.U.M.M.O.N. provides a way to describe such things formally, in a JSON file - and later execute them *automagically* (without millions of people all over the world spending their time to press exactly the same buttons, and without silly mistakes/typos either - computers having MUCH better attention to detail than humans). 
    + moreover, in most of the cases S.U.M.M.O.N. is able to figure out "how the mod was installed months ago by another mod manager" (i.e. post-factum) - and to make JSON instructions out of the existing setup. See <sup>(*)</sup> note below, but we are already able to reconstruct "how it was installed" for 90% of the mods in a pre-existing RL fairly modest 300-mod MO2 setup (to achieve it, our script has to run hundreds of thousands of FOMOD simulations, try multiple patchers and detect multiple tools, and so on and so forth - but here we are, and the script finishes within 5 minutes too). 
  * Our aim is that an end-user should be able to install S.U.M.M.O.N., and then just to tell S.U.M.M.O.N. - "hey, I want to install S.T.E.P." - and then go to sleep to find out in the morning that all the heavy-lifting was done for them by S.U.M.M.O.N.
2. S.U.M.M.O.N. generalizes such *automated install guides* to a more generic concept of "mod packs". In general, "mod pack" is a bunch of mods (ranging from single mod to the whole setup), which can be installed AND upgraded *fully automatically*.
  * Note stark constrast with modlist managers such as Wabbajack - unlike Wabbajack setups, S.U.M.M.O.N. modpacks are (a) highly modular, (b) very small (as in "100 Kbytes for S.U.M.M.O.N." vs "1 GByte for Wabbajack" for the same setup), and (c) most of the time are *automatically upgradable* (the very same way S.T.E.P. setup is automatically upgradeable - by simply downloading new versions and applying installation instructions again).
  * In turn, "mod packs" will allow modder community to finally start separating responsibilities, where each modder needs to be a specialist only on one single subject matter, borrowing expertise of the others in other areas. For example, if modder A is interested in quests, they can re-use "mod packs" for environment, and for Bodyslide+3BA, and for FNIS and/or Nemesis, and so on, concentrating their efforts on that one thing which THEY want to deal with. 
  * As modpacks are mostly-text JSON-based instructions, S.U.M.M.O.N. relies on them being published on GitHub, facilitating reuse. 
3. S.U.M.M.O.N. knows (and shows) not only information on "from which archive this mod on your disk was installed", but also "how it was installed", and "what has changed afterwards". If some file or mod has been modified from original install (by some tool, or by you accidentally unpacking some archive where it doesn't belong, or for any other reason) - we'll detect it right away, and will tell you about it. We are [omniscient](https://en.wiktionary.org/wiki/omniscient) (="we know EVERYTHING") - and will happily share this knowledge with the modder.
4. S.U.M.M.O.N. uses git to store projects, with the projects being source-control-friendly (in S.U.M.M.O.N. speak - "stable") JSON files - which means that user has access to the whole history of their work, can see "what has changed since this point in time", and can easily roll back if necessary. 
  * as long as your project is in GitHub, you don't need to release huge modlist files a-la Wabbajack - *all the information necessary to allow the others to assemble an exact (or not-so exact, see above re. upgrades) project, is already in this JSON file with automated installation instructions*  
  * while currently S.U.M.M.O.N. supports only "public" projects in GitHub, we're planning to add support for "private" projects with local git pretty soon.

<sup>(*)</sup> - yes, we do know that these claims sound "too good to be true"; however, we have at least working proofs-of-concepts for these things. 

## Technology Behind
* Python (while we're mostly C++ company, but for this kind of things using C++ would mean like 5x more work). To put it into perspective - while MO2 has a codebase of around 80K LoC, we currently have around 10K, and hope to be within 20K LoC when we have a full-scale mod manager (with MUCH more functionality than MO2). 
  + and yes, making things fast is possible in Python too; our code uses well-encapsulated multiprocessing to perform things in parralel while preventing GIL from becoming a bottleneck.
  + to provide traditional installer executable, we're using *bootstrapper* - a funny piece of code, which makes an installer exe out of our Python code (using `pyinstaller`), which installer exe can download and install latest-greatest Python and git, and then install all the necessary PyPi modules, and then get and run our current code from this very GitHub project. 
* reliance on file crypto-hashes (we're using SHA-256) as file identifiers. For example, if one user has unpacked archive with crypto-hash H0 and found that it consists of N files with hashes H1...HN, then they can share this information of {H0:[H1,...,HN]} (in our case - via GitHub), and then WHOEVER who got archive with crypto-hash H0, can be 100% sure which files are within this archive - and with which per-file hashes - *without even unpacking the archive*
  + to give the credit where credit is due, AFAWK the first folks who used hashes as globally-unique file IDs in the modding context, were folks from [Wabbajack](https://www.wabbajack.org/), but we take it to the whole new level. 
* widespread use of .py plugins (we already have 7 different *types* of plugins - and counting). We have plugins for unarchivers (.7z/.rar/.zip), and for archive installers (BAIN/FOMOD/MO2), and for globaltools (such as BodySlide), and for 3rd-party mod managers, and for modtools, and for fileorigins (such as Nexus/LL), and for patchers (as in "please add these two `[section]+name->value` lines to an existing .ini file").
  + we also plan to add UI plugins (so user can choose which UI they prefer)
  + and as it is Python, it means that to add your own plugin, you just need to drop your .py file into respective folder. 
* concept of "readily-available in-memory information about the WHOLE setup". After initial re-scan (except for the very first time, it shouldn't take more than 5-10 seconds), we know *everything* about current state of your modding setup (in our Python code, it is `class OmniCache`).

## Current Status
We are currently at the stage where we have a very decent prototype. Major items missing are:
  * UI
  * OS-level monitoring of file changes (to reduce the need for relatively expensive stats re-scans)
  * refactoring to complete migration to new 'stable json' format
  * overriding LOOT ordering in mod packs
  * VFS (adding it won't be *too* difficult, as we'll use hard-links as Vortex, but we already have technology to detect changes within seconds after running program finishes, and will move modified files to overwrite if there are any, restoring pristine state of your mod installs)
    + BTW, we also want to provide copy-on-write-based VFS too (copy-on-write on Windows is supported by ReFS, and ReFS is supported on desktop Win 11 for a long while via Dev Drive, but Win 11 24H2 reportedly added support for ReFS without Dev Drive too, though not for C: drive yet); for copy-on-write VFS, "healing" in case of the tool messing with "pristine" mod install, is expected to be MUCH faster.
  * lots of plugins (among most important ones - tools plugins, Vortex plugin, .esp patch plugin, LL plugin)
  * adding missing features for install guides (most importantly - S.T.E.P.), and for current Wabbajack users.

Expected time frame for public but closed beta (="selected folks for Nexus/LL, hopefully some S.T.E.P. folks") - 3 months *since we manage to hire ppl as described below.* Which means that **if you REALLY want all these features AND qualify - come work to us!** :wink:

## We're HIRING!
Current status above means that there is still a Damn Lot(tm) of work. And to finalize it ASAP, we're currently HIRING people, with the following qualifications:
* passion for modding
* extensive modding experience (preferably Skyrim or FO), using mod manager, with at least 100+ mods in a single setup (no, "just this one mod" won't do), and using at least some of the tools such as BodySlide and/or FNIS/Nemesis.
* serious Python experience, preferably production-level.
  + take a look at the code in this very GitHub project (in `summonmm` folder) - would you be comfortable working with it?
* at least understanding why source control is a Good Thing(tm)

**If you qualify and want to become one of the authors of the next-gen mod manager - make sure to write to dream.team@6it.dev**

FAQ:
* yes, we'll be paying money which are competitive with usual rates for seasoned Python developers
* it is 100% remote, so self-discipline is Damn Important(tm)
  + on the plus side, you can be *anywhere in the world* (though being within +-2 hours from Central Europe is a plus)
* formally - it is a contract with an Irish company with a per-hour rate
