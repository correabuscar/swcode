#!/usr/bin/pypy3 -bb
# SPDX-License-Identifier: (GPL-3.0-only OR GPL-2.0-only OR LGPL-2.0-only OR LGPL-2.1-only OR LGPL-3.0-only OR AGPL-3.0-only OR MIT OR MIT-0 OR BSD-2-Clause OR BSD-3-Clause OR CC0-1.0 OR Unlicense OR 0BSD OR Apache-2.0)
#TODO: add mozilla license? add more licenses; and change file LICENSE.spdx too!

#TODO: currently made to work specifically only on my Z575 computer... Maybe make this more generic?

#TODO: find a name for it:
#renamed from cutectrl 0.1.4 to cuspctrl 0.1.5 on 02Sept2020
#cpu speed temperature-based control = cusptebactrl
#cpu speed control = cuspctrl = cpu speed control based on temperature = cuspcbot
#atectrl or atecpuctrl = automatic temperature-based CPU control
#automatically controls CPU speed to be within certain maximum temperature threshold
#ctectrl or cutectrl or cutecpuctrl = cpu temperature control  (no results for the latter on ddg)  - don't use this because it make me think acutectrl

#learning python... started with https://wiki.python.org/moin/SimplePrograms

#interesting, about two weeks later(after making that keeping proc files open and seek/read when needed here), I see this: https://www.phoronix.com/scan.php?page=news_item&px=Linux-READFILE-System-Call

from __future__ import print_function
import os,sys
import glob
# glob supports Unix style pathname extensions
# glob from src: https://wiki.python.org/moin/SimplePrograms
import time
from typing import List, TextIO, Any, Optional, Set
#from typing import Final #doesn't work with pypy3, ImportError: cannot import name 'Final'
import atexit
#import sys
import fcntl
import subprocess,shlex
#from subprocess import CompletedProcess
import io

import signal
#import enum
#import types
from types import FrameType# as FrameType

import math #for math.ceil()

#-----
import sys #i know it's already imported, but just making sure this whole block can be moved before the prev. import, if ever.
oldsyspath=sys.path
sys.path.append("/swcode/")
import swcode
sys.path=oldsyspath
#-----

#globals:
max_seen_temp:Optional[float] = None
min_seen_temp:Optional[float] = None

#src: https://stackoverflow.com/questions/287871/how-to-print-colored-text-in-terminal-in-python/287944#287944
#class bcolors: #b doesn't mean background
class _BColors(swcode.Constants):
    __slots__ = () #required for Constants

    #HEADER = '\033[95m'
    #OKBLUE = '\033[94m'
    #OKGREEN = '\033[92m'
    RED = '\033[91m'
    BG_RED="\x1B[41m" #tput setab 1
    BG_DARKRED="\x1B[48;5;52m" #tput setab 52
    FAIL = '\033[41m'
    WARN = '\033[38;5;91m'
    #ENDC = '\033[0m'
    ENDC = '\033(B\033[m' #aka reset aka `tput sgr0`
    RESET="\x1B(B\x1B[m" #tput sgr0, in xfce4-terminal, TERM=xterm-256color
    #BOLD = '\033[1m'
    #UNDERLINE = '\033[4m'
    DEBUG = '\033[90m'
    BG_GREEN="\x1B[42m" #tput setab 2
#doneTODO: add the other colors eg. color_green to this list and use this method! (forgot about this due to months of break from coding this)

bcolors=_BColors()
del _BColors #because we should use the instance, instead.

#PROGRAM_VERSION: Final = "0.0.26"

def colored(color: str, text: str) -> str:
    return f"{color}{text}{bcolors.ENDC}"

def anymsg(color:str, prefix:str, *anything_to_conv_to_str:Any) -> str:
    return colored(color, prefix + ' '.join(str(element) for element in anything_to_conv_to_str))

#def redmsg(msg:str) -> str:
#    return colored(bcolors.RED, msg)
def redmsg(*anything:Any) -> str:
    return anymsg(bcolors.RED, "", *anything)

#def warn(msg: str) -> None:
#    eprint(colored(bcolors.WARN,"Warning: "+msg))

#takes any number or args
def debugmsg(*anything:Any) -> str:
    #return colored(bcolors.DEBUG,"Debug: "+ str(anything))
    return colored(bcolors.DEBUG,"Debug: "+ ' '.join(str(element) for element in anything))

def warnmsg(*anything:Any) -> str:
    return colored(bcolors.WARN,"Warning: "+ ' '.join(str(element) for element in anything))

def failmsg(*anything:Any) -> str:
    return colored(bcolors.FAIL,"Fail: "+ ' '.join(str(element) for element in anything))

#def debugpr(msg:str) -> None:
#    eprint(debugmsg(msg))

def debugpr(*args: Any, **kwargs: Any) -> None:
    #XXX: I don't want to put the "if __debug__:" inside this! because I want this to be callable from release (aka -OO arg of pypy3)
    eprint(debugmsg(*args), **kwargs)

def warn(*args: Any, **kwargs: Any) -> None:
    eprint(warnmsg(*args), **kwargs)
    #done: how to add red color on the text here?

#sprint src: https://stackoverflow.com/questions/5309978/sprintf-like-functionality-in-python/56103429#56103429
def sprint(*args: Any, **kwargs: Any) -> str:
    sio = io.StringIO()
    print(*args, file=sio, **kwargs)
    return sio.getvalue()

def fail(*args: Any, **kwargs: Any) -> None:
    fstr=sprint(failmsg(*args), end='', **kwargs)
    eprint(fstr)
    raise Exception(fstr)

#nvm this, decided to do it in another way, from inside swcode!
##constant src: https://stackoverflow.com/questions/2682745/how-do-i-create-a-constant-in-python/2688086#2688086
##Any src: https://stackoverflow.com/questions/39817081/typing-any-vs-object/39817126#39817126
#def constant(f: Any) -> property:
#    def fset(self: Any, value: Any) -> None:
#        #raise TypeError(f"{bcolors.FAIL}Constants cannot be set{bcolors.ENDC}")
#        #raise TypeError(colored(bcolors.FAIL,"Constants cannot be set"))
#        raise TypeError(redmsg("Constants cannot be set"))
#    def fget(self: Any) -> Any:
#        return f(self)
#    return property(fget, fset)

#class _Const_program(object):
#    @constant
#    def VERSION(self) -> str:
#        return "0.1.14" #program version
#    @constant
#    def NAME(self) -> str:
#        return "cuspctrl"

class _Const_program(swcode.Constants):
    __slots__ = () #required
    VERSION:str = "0.1.17" #program version
    #^ based on c p u v a r y v0.0.25 which was written in bash.
    NAME:str = "cuspctrl"

#class _Const_Z575(object):
#    @constant
#    def EXPECTED_TFILES(self) -> int:
#        return 6
#    @constant
#    def EXPECTED_SPEEDFILES(self) -> int:
#        return 4  #number of physical cores (so, excluding hyperthreading ones)
#    @constant
#    def KNOWN_MIN_SPEED(self) -> int:
#        return 800000 #value from /sys/devices/system/cpu/cpufreq/policy0/scaling_min_freq
#        #hardcoding these here, because they are known min/max for this computer.
#    @constant
#    def KNOWN_MAX_SPEED(self) -> int:
#        return 1400000 #value from /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq

class _Const_Z575(swcode.Constants):
    __slots__ = () #required
    EXPECTED_TFILES: int = 6
    EXPECTED_SPEEDFILES: int = 4
    #^ number of physical cores (so, excluding hyperthreading ones)
    KNOWN_MIN_SPEED: int = 800000
    #^ value from /sys/devices/system/cpu/cpufreq/policy0/scaling_min_freq
    #hardcoding these here, because they are known min/max for this computer.
    KNOWN_MAX_SPEED: int = 1400000
    #^ value from /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq

#hardcoding paths to avoid some security issues when executing them with PATH being set by user somehow. Would this fail on NixOS or does it have symlinks to the real ones? probably the latter case.
class _Const_OS(swcode.Constants):
    __slots__ = () #required
    MOUNT:str="/usr/bin/mount"
    GREP:str = "/usr/bin/grep"
    SHELL:str = "/bin/sh"
    CPUPOWER:str = "/usr/bin/cpupower"

#class _Const_OS(object):
#    @constant
#    def MOUNT(self) -> str:
#        return "/usr/bin/mount"
#    @constant
#    def GREP(self) -> str:
#        return "/usr/bin/grep"
#    @constant
#    def SHELL(self) -> str:
#        return "/bin/sh"
#    @constant
#    def CPUPOWER(self) -> str:
#        return "/usr/bin/cpupower"

#class _Const_pconsts(object):
#    @constant
#    def IMPLEMENT_TMUX_STUFF(self) -> bool:
#        return False #to avoid output during window title setting via set_xwindow_title()
#    @constant
#    def DOLLAR0(self) -> str:
#        dollar0=os.path.realpath(__file__) #aka $0 in bash, ie. `realpath -- "$0"`  unless this code resides inside a python module!
#        if __debug__:
#            arg0=os.path.realpath(sys.argv[0])
#            assert arg0 == dollar0, f"Problem detected: argv[0] and __file__ don't match(after realpath solved): '{arg0}' vs '{dollar0}'"
#        return dollar0
#    @constant
#    def LOCK_FILENAME(self) -> str:
#        #f=os.path.realpath(__file__) #aka self or $0 in bash
#        bnf=os.path.basename(self.DOLLAR0)
#        return "/var/run/{bnf}.lock".format(bnf=bnf)
#    @constant
#    def USER(self) -> str:
#        return os.getlogin()
#    @constant
#    def MAXTEMP(self) -> float:
#        return 78.0
#    @constant
#    def MINTEMP(self) -> float:
#        assert type(CONST.TEMPTHRESH) is float, debugmsg(type(CONST.TEMPTHRESH))
#        assert type(CONST.MAXTEMP) is float, debugmsg(type(CONST.MAXTEMP))
#        #/usr/bin/mypy is owned by mypy 0.770-1  in ArchLinux
#        #/usr/bin/pypy3 is owned by pypy3 7.3.1-1
#        #mypy --python-executable=/usr/bin/pypy3 --strict /dev/null "./$srcfile"
#        #The following line doesn't work here, mypy said: cutectrl.py:111: error: Returning Any from function declared to return "float"
#        #even though both vars are float!
#        #return self.MAXTEMP - self.TEMPTHRESH
#        #But these work:
#        #return float(self.MAXTEMP) - float(self.TEMPTHRESH)
#        return float(self.MAXTEMP - self.TEMPTHRESH)
#        #fail:
#        #return self.MAXTEMP - self.TEMPTHRESH
#    @constant
#    def TEMPTHRESH(self) -> float:
#        return 2.0
#    @constant
#    def SLEEPTIME(self) -> float:
#        #in seconds
#        return 0.5
#    @constant
#    def INCREASE_SLEEPTIME_AFTER_X_SECONDS_OF_CONSTANT_UNDER_MINTEMP(self) -> float:
#        #so, if the temperature is constantly(uninterrupted by jumping over MAXTEMP for example) under MINTEMP for this amount of seconds, then the sleep time will be increased
#        #in seconds
#        return 20
#    @constant
#    def SLEEPTIME_MOST(self) -> float:
#        #in seconds
#        return 1
#    @constant
#    def SLEEPTIME_LEAST(self) -> float:
#        #in seconds
#        return 0.1
#    @constant
#    def MAXLINELENGTH(self) -> int:
#        return 300

class _Const_pconsts(swcode.Constants):
    __slots__=() #required
    IMPLEMENT_TMUX_STUFF:bool=False
    DOLLAR0:str = os.path.realpath(__file__) #aka $0 in bash, ie. `realpath -- "$0"`  unless this code resides inside a python module!
    LOCK_FILENAME: str = "/var/run/{bnf}.lock".format(bnf=os.path.basename(DOLLAR0))
    USER:str =os.getlogin()
    MAXTEMP:float = 78.0
    TEMPTHRESH:float = 2.0
    #MINTEMP:float = float(MAXTEMP - TEMPTHRESH)
    #TODO: need a way to prevent fields from referencing globals when they're trying to reference fields, ie. https://paste.debian.net/1162827/
    MINTEMP:float = MAXTEMP - TEMPTHRESH
    SLEEPTIME:float = 0.5 #in seconds
    INCREASE_SLEEPTIME_AFTER_X_SECONDS_OF_CONSTANT_UNDER_MINTEMP:float = 20 #after how many seconds
    #^ so, if the temperature is constantly(uninterrupted by jumping over MAXTEMP for example) under MINTEMP for this amount of seconds, then the sleep time will be increased
    SLEEPTIME_MOST: float = 1.0 #in seconds
    SLEEPTIME_LEAST:float = 0.1 #in seconds
    MAXLINELENGTH:int = 300 #after this many chars (or is it prints) echo a \n
    def __init__(self) -> None:
        #if __debug__:
        if True: #I don't wanna un-indent
            #some sanity checks:
            #for DOLLAR0
            dollar0=self.DOLLAR0
            arg0=os.path.realpath(sys.argv[0])
            assert arg0 == dollar0, f"Problem detected: argv[0] and __file__ don't match(after realpath solved): '{arg0}' vs '{dollar0}'"
            #end DOLLAR0
            assert type(self.TEMPTHRESH) is float, debugmsg(type(self.TEMPTHRESH))
            assert type(self.MAXTEMP) is float, debugmsg(type(self.MAXTEMP))
            assert type(self.MINTEMP) is float, debugmsg(type(self.MINTEMP))

#TODO: use a general var here and set it depending on the hostname, to either Z575 or some other host's expected constants.
Z575 = _Const_Z575()
del _Const_Z575
PROGRAM = _Const_program()  #so print(PROGRAM.VERSION) shows that.
del _Const_program
#PROGRAM.VERSION="1" #cannot be set
CONST = _Const_pconsts()  #don't forget these parens! else you get <property object at 0x00007f4a83140920> when referencing the constants!
del _Const_pconsts
CONSTOS = _Const_OS()
del _Const_OS

#The temperature files in /proc will be kept open and just seek(0) before any read, to avoid open/close on each read!
temperature_openfiles_list: List[TextIO] = []
temperature_fileglobs_list: List[str] = [
        '/sys/devices/pci*/*/hwmon/hwmon*/temp*_input',
        '/sys/devices/virtual/thermal/thermal_zone*/hwmon*/temp*_input',
        '/sys/devices/virtual/thermal/thermal_zone*/hwmon*/temp*_input',
        #'/inexistent/crap', #this would just cause a warning for now
        ]
#the expanded globs, held here: #expanded from temperature_fileglobs_list
temperature_filenames_list: List[str] = [] #expanded at runtime

#doneTODO: not yet implemented these:
setspeed_openfiles_list: List[TextIO] = []
setspeed_fileglobs_list: List[str] = [
        '/sys/devices/system/cpu/cpufreq/policy*/scaling_setspeed' #using '*' instead of '?' just in case there are more than 10 logical processor, which there will be! eg. 11
        ]
setspeed_filenames_list: List[str] = [] #expanded at runtime



def set_xwindow_title(title: str) -> None:

    #XXX: note: using eprint to print the title(s) to stderr so that in case of not running under tmux OR xfce4-terminal, then the output won't interfere with normal stdout output, should it ever be piped for use by other programs!

    #xfce4-terminal window title (had no effect if tmux is running inside it!)
    eprint(f"\033];{title}\a", end='')

    if CONST.IMPLEMENT_TMUX_STUFF:
        #XXX: detecting whether or not we're under tmux here is problematic, if running under 'sudo' the TMUX env. var. won't be inherited, thus checking for it won't be good enough to detect TMUX.

        #tmux window title(seen as a tab at the left status bar only)
        eprint(f"\033k{title}\033\\", end='')

        #tmux pane title (used as window title, in place of xfce4-terminal window title) aka window title if tmux is running inside xfce4-terminal
        eprint(f"\033]2;{title}\033\\", end='')
        #^ depending on ~/.tmux.conf settings the above won't replace the window title!
        #you may need something like:
        #set -g set-titles on
        #set -g set-titles-string "#H #{pane_title} #{pane_current_path} LA:#{t:client_activity}"
        #ie. it uses #{pane_title} to set the window title! so that's what {title} in the above printf will become: #{pane_title}

    sys.stderr.flush()



def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)

def expand_globs(glob_list: List[str]) -> List[str]:
    expanded_list: List[str] = []
    for each_glob in glob_list:
        gret = glob.glob(each_glob, recursive=False)
        if len(gret) == 0:
            warn("Missing expansion for glob '{glob}'".format(glob=each_glob))
        expanded_list += gret
    expanded_list.sort() #because for wtw reason, the list isn't sorted like 'echo' of bash sees it, eg. policy{0..3} is unsorted like policy{2,0,3,1}
    return expanded_list

def expand_tglobs() -> None:
    temperature_files: List[str] = []
    global temperature_fileglobs_list  #XXX: hmm, it worked without this, why?
    assert len(temperature_fileglobs_list) > 0, debugmsg("should have at least one element in 'temperature_fileglobs_list' var")
    #assert temperature_files != temperature_fileglobs_list, debugmsg("Remnant from a previous assignment which is found below: temperature_filenames_list = temperature_files") #never hit, because this isn't how it works, gladly! not sure wtf I tried to find here, it doesn't make sense.
    temperature_files=expand_globs(temperature_fileglobs_list)
    #for each_glob in temperature_fileglobs_list:
    #    gret = glob.glob(each_glob, recursive=False)
    #    if len(gret) == 0:
    #        warn("Missing expansion for glob '{glob}'".format(glob=each_glob))
    #    temperature_files += gret
    #print(type(temperature_files))
    #temperature_files += glob.glob('/sys/devices/pci*/*/hwmon/hwmon*/temp*_input', recursive=False)
    #print(type(temperature_files))
    #temperature_files += glob.glob('/sys/devices/virtual/thermal/thermal_zone*/temp', recursive=False)
    #temperature_files += glob.glob('/sys/devices/virtual/thermal/thermal_zone*/hwmon*/temp*_input', recursive=False)
    #print(temperature_files, len(temperature_files));
    if __debug__: #In the current implementation, the built-in variable __debug__ is True under normal circumstances, False when optimization is requested (command line option -O).
        _expected = Z575.EXPECTED_TFILES
        _have = len(temperature_files)
        assert _expected == _have, warnmsg("Not all {expected} temperature sensors were detected, Found({have}): {listthem}".format(have=_have, expected=_expected, listthem=temperature_files))
    global temperature_filenames_list
    temperature_filenames_list = temperature_files
    if __debug__:
        #useless double check
        assert _expected == len(temperature_filenames_list), debugmsg(temperature_filenames_list)

def expand_speedglobs() -> None:
    speed_files: List[str] = []
    global setspeed_fileglobs_list  #XXX: hmm, it worked without this, why?
    assert len(setspeed_fileglobs_list) > 0, debugmsg("should have at least one element in 'setspeed_fileglobs_list' var")
    #assert speed_files != setspeed_fileglobs_list, debugmsg("Remnant from a previous assignment which is found below: setspeed_filenames_list = speed_files") #never hit, because this isn't how it works, gladly! not sure wtf I tried to find here, it doesn't make sense.
    speed_files=expand_globs(setspeed_fileglobs_list)
    if __debug__: #In the current implementation, the built-in variable __debug__ is True under normal circumstances, False when optimization is requested (command line option -O).
        _expected = Z575.EXPECTED_SPEEDFILES
        _have = len(speed_files)
        assert _expected == _have, warnmsg("Not all {expected} setspeed files were detected, Found({have}): {listthem}".format(have=_have, expected=_expected, listthem=speed_files))
    global setspeed_filenames_list
    setspeed_filenames_list = speed_files
    if __debug__:
        #useless double check
        assert _expected == len(setspeed_filenames_list), debugmsg(setspeed_filenames_list)

def close_tfiles() -> None:
    global temperature_openfiles_list

    if __debug__:
        cloned=temperature_openfiles_list.copy()

    if __debug__:
        debugpr("Closing temperature files:")
    while temperature_openfiles_list:
        #close in normal order(top to bottom)
        tfile = temperature_openfiles_list.pop(0)
        if __debug__:
            debugpr(tfile.name)
        tfile.close()
        assert tfile.closed, debugmsg(tfile.name)

    if __debug__:
        for tfile in cloned:
            assert tfile.closed, debugmsg(tfile.name)

    atexit.unregister(close_tfiles)

#TODO: do something about this code repetition: close_speedfiles and close_tfiles
def close_speedfiles() -> None:
    global setspeed_openfiles_list

    if __debug__:
        cloned=setspeed_openfiles_list.copy()

    if __debug__:
        debugpr("Closing speed files:")
    while setspeed_openfiles_list:
        #close in normal order(top to bottom)
        sfile = setspeed_openfiles_list.pop(0)
        if __debug__:
            debugpr(sfile.name)
        try:
            sfile.close() # this happens "OSError: [Errno 22] Invalid argument" when cuspctrl is running with opened speed files and then I run: "sudo /usr/bin/cpupower frequency-set --related --governor performance --min 800MHz --max 1000MHz"
        except OSError as e:
            debugpr(f"Failed to close speed file {sfile}: {e}")
        assert sfile.closed, debugmsg(sfile.name)

    if __debug__:
        for sfile in cloned:
            assert sfile.closed, debugmsg(sfile.name)

    atexit.unregister(close_speedfiles)

@atexit.register
def exitHandler() -> None:
    if __debug__:
        debugpr("exitHandler for '{self}'.".format(self=CONST.DOLLAR0))
    #close_tfiles() #not here!
    #close_speedfiles() #not here!
    if min_seen_temp is not None:
        print(f"Min seen temp: {min_seen_temp}C.")
    if max_seen_temp is not None:
        print(f"Max seen temp: {max_seen_temp}C.")
    print("Pausing to allow screen to be read. Press Enter or Ctrl+D to exit (or Ctrl+C, wtw)", end="")
    sys.stdout.flush() #to see the prev. line due to no eoln outputted meaning no flush
    got:str=sys.stdin.readline()
    if len(got) == 0:
        #ie. Ctrl+D
        print()
    #else, pressed Enter or C-c

def open_tfiles() -> None:
    expand_tglobs()
    if __debug__:  #yes, twice
        expand_tglobs()
    global temperature_openfiles_list
    temperature_openfiles_list = []
    global temperature_filenames_list
    assert 0 < len(temperature_filenames_list), debugmsg("No temperature files were found:{list}".format(list=temperature_filenames_list))
    if __debug__:
        debugpr("Opening temperature files:")
    for temperatur_file in temperature_filenames_list:
        if __debug__:
            debugpr(temperatur_file)
        tfile:TextIO = open(temperatur_file, mode='r', buffering=1, closefd=True)
        #1 to select line buffering (only usable in text mode)
        #note: closefd can never be False when filename is given; so this is more like stating the obvious/default(s)

        #print(type(tfile))
        assert not tfile.closed, debugmsg(tfile)
        temperature_openfiles_list.append(tfile)
    atexit.register(close_tfiles)

def open_speedfiles() -> None:
    expand_speedglobs()
    if __debug__:  #yes, twice
        expand_speedglobs()
    global setspeed_openfiles_list
    setspeed_openfiles_list = []
    global setspeed_filenames_list
    assert 0 < len(setspeed_filenames_list), debugmsg("No speed files were found:{list}".format(list=setspeed_filenames_list))
    if __debug__:
        debugpr("Opening speed files:")
    for speed_file in setspeed_filenames_list:
        if __debug__:
            debugpr(speed_file)
        sfile:TextIO = open(speed_file, mode='w+', buffering=1, closefd=True)
        #w+ means read and write
        #0 means unbuffered -- "ValueError: can't have unbuffered text I/O"
        #1 to select line buffering (only usable in text mode)
        #note: closefd can never be False when filename is given; so this is more like stating the obvious/default(s)

        #print(type(sfile))
        assert not sfile.closed, debugmsg(sfile)
        setspeed_openfiles_list.append(sfile)
    atexit.register(close_speedfiles)

#TODO: find 'assert'`s source code and see if we can implement dassert as a wrapper for `assert cond, debugmsg(msg)` as `dassert cond,msg` // unclear how to do this if assert is in Python/ast.c

def get_current_speeds() -> List[int]:
    #current CPU speeds for each physical core
    speeds: List[int] = []
    global setspeed_openfiles_list
    for sfile in setspeed_openfiles_list:
        #time.sleep(1) #temporary, to help with C-c pressing
        try:
            sfile.seek(0)
        except OSError as e:
            debugpr(f"Failed to seek to 0 in speed in {sfile}: {e}")
            #close_speedfiles()
            #open_speedfiles()
            if ensure_cpu_governor_is("userspace") == "userspace":
                debugpr(f"governor was already 'userspace' and seeking still failed, raising {e}")
                raise e
            continue
        first_line = sfile.readline().strip() #eg. 1400000 for Z575
        if not first_line.isdigit():
            if "<unsupported>" == first_line:
                cg=get_current_cpu_governor()
                debugpr(f"Governor is, presumably, no longer 'userspace', it's '{cg}'. Attempting to change back.")
                #XXX: eg. governor is not 'userspace', it's something like 'performance'
                if ensure_cpu_governor_is("userspace") == "userspace":
                    debugpr(f"Well, governor was already 'userspace' and was still getting 'unsupported' for setspeeds, raising new RuntimeError exception.")
                    raise RuntimeError("Unusual circumstance")
                continue
            else:
                raise RuntimeError("unknown situation")
        if __debug__:
            assert first_line.strip().isdigit(), debugmsg(first_line)
        if __debug__:
            second_line = sfile.readline() #eg. nothing!
            assert second_line == "", debugmsg(second_line)
            #print(second_line)
        val1 = int(first_line, base=10)
        #TODO: handle(outside of __debug__) this case: ValueError: invalid literal for int() with base 10: '<unsupported>\n'
        #that happens when cuspctrl is running and you run: sudo /usr/bin/cpupower frequency-set --related --governor performance --min 800MHz --max 1000MHz
        #print(val1)
        assert Z575.KNOWN_MIN_SPEED <= val1 <= Z575.KNOWN_MAX_SPEED, debugmsg(val1)
        if __debug__:
            sfile.seek(0)
            #time.sleep(1) #temporary, to help with C-c pressing
            refl = sfile.readline()
            val2 = int(refl, base=10)
            #debugpr(val1, val2) #they may not be equal tho
            assert Z575.KNOWN_MIN_SPEED <= val2 <= Z575.KNOWN_MAX_SPEED, debugmsg(val1)
        speeds.append(val1)
    return speeds #can be empty due to 'continue' when it yields 'unsupported'

def get_current_speed() -> Optional[int]:
    speeds: List[int] = get_current_speeds()
    if len(speeds) <= 0:
        return None
    first=speeds[0]
    maxx=max(speeds)
    if __debug__:
        for corenum,speed in enumerate(speeds, start=0):
            if first != speed:
                warn("Core #{corenum} has differently set current speed({speed} vs expected {first}), speeds={speeds}. Current speed will be reported as max (ie. {maxx})".format(corenum=corenum,speeds=speeds, speed=speed, first=first, maxx=maxx))
    return maxx

def set_current_speed(to: int) -> Optional[int]:
    assert Z575.KNOWN_MIN_SPEED <= to <= Z575.KNOWN_MAX_SPEED, debugmsg(to)
    #hmmTODO: do I return prev. speed or the current speed after having set it to 'to' ?
    #ret = get_current_speed()
    global setspeed_openfiles_list
    for sfile in setspeed_openfiles_list:
        if __debug__:
            try:
                sfile.seek(0)
            except OSError as e:
                debugpr(f"Failed to seek to 0 in speed in {sfile}: {e}")
                #close_speedfiles()
                #open_speedfiles()
                if ensure_cpu_governor_is("userspace") == "userspace":
                    debugpr(f"governor was already 'userspace' and seeking still failed, raising {e}")
                    raise e
                continue
            before_speed_str: str= sfile.readline().strip()
            #before_speed_int: int = 0 #value to show when 'unsupported'
            #if before_speed_str.isdigit():
            #    before_speed_int = int(before_speed_str, base=10)
        sfile.seek(0)
        #debugpr("About to write:",to) #ok this is 800000 and it still fails with "OSError: [Errno 22] Invalid argument" if I run this while cuspctrl is running: "sudo /usr/bin/cpupower frequency-set --related --governor performance --min 800MHz --max 1000MHz"
        try:
            sfile.write(str(to))
            sfile.flush() #this flush aka sync is very much necessary due to line buffering being a requirement for TextIO ie. "ValueError: can't have unbuffered text I/O", or I can add a new line to the above write, maybe (untested)
        except OSError as e:
            debugpr(f"Failed to write {to} to speed in {sfile}: {e}")
            #close_speedfiles()
            #open_speedfiles()
            if ensure_cpu_governor_is("userspace") == "userspace":
                debugpr(f"governor was already 'userspace' and write/flush still failed, raising {e}")
                raise e
            continue
        #if __debug__: #ok, need this block to run when non-debug too! or else won't be able to rectify governor changes
        if True:
            #time.sleep(1) # temporary
            sfile.seek(0)
            speed_now_str: str= sfile.readline()
            speed_now_int: int = int(speed_now_str, base=10)
            if speed_now_int != to:
                warn("Immediately setting the speed to {to} failed, readback was {now}. Possibly something else got a chance to change it(shouldn't happen more than once), or likely the max speed aka scaling_max_freq was just set to {now} by something else(eg. 'cpupower') thus it will ignore anything above that, or(unlikely) writing the new speed({to}) had no effect(prev. was {before_speed_str} ) for unknown reasons. Will next reset governor to 'userspace' and set min/max. If this keeps repeating unendingly, it's a bug in this code.".format(to=to, now=speed_now_int, before_speed_str=before_speed_str));
                ensure_cpu_governor_is("userspace")
                #if ensure_cpu_governor_is("userspace") == "userspace":
                #    raise RuntimeError("")
                ensure_cpu_min_max_limits_are_set()
    ret = get_current_speed()
    if ret is None:
        return None
    if __debug__:
        after_speed = ret
        if after_speed != to:
            warnmsg("Failed to set speed to {to}, it's {now}".format(to=to,now=after_speed))
    return ret

def get_temperatures() -> List[float]:
    temps: List[float] = []
    global temperature_openfiles_list
    for tfile in temperature_openfiles_list:
            tfile.seek(0)
            first_line = tfile.readline() #eg. 45000 for 45 degC
            if __debug__:
                assert first_line.strip().isdigit(), debugmsg(first_line)
            if __debug__:
                second_line = tfile.readline() #eg. nothing!
                assert second_line == "", debugmsg(second_line)
                #print(second_line)
                val1 = int(first_line, base=10)
                float1 = val1 / 1000 # eg. 45.0
            else:
                float1 = int(first_line, base=10) / 1000 #eg. 45.75
            assert 0 <= float1 <= 120, debugmsg(float1)
            if __debug__:
                tfile.seek(0)
                #time.sleep(1) #temporary, to help with C-c pressing
                refl = tfile.readline()
                val2 = int(refl, base=10)
                float2 = val2 / 1000;
                #debugpr(val1, val2, float1, float2)
                assert 0 <= float2 <= 120, debugmsg(float2)
            temps.append(float1)
    return temps

def get_temperatur() -> float:
    return max(get_temperatures())

def ensure_not_already_running(use_self_as_lock_file:bool=False) -> None:
    # Ensures only one instance of this script is ran
    # note: this works even if script is running as different user
    if use_self_as_lock_file:
        f=os.path.realpath(__file__) #aka self or $0 in bash, works just fine if it's a hardlink or symlink ! or another user running it!
        #f=CONST.DOLLAR0
        assert f == CONST.DOLLAR0, debugmsg("or else broken code somewhere, ie. DOLLAR0")
    else:
        f=CONST.LOCK_FILENAME

    if __debug__:
        debugpr("Using lock file '{f}' to prevent this script from running more than once!".format(f=f))
    if (f == CONST.LOCK_FILENAME) and (not use_self_as_lock_file):
        mode='x' #'x' open for exclusive creation, failing if the file already exists
    elif (f != CONST.LOCK_FILENAME) and (use_self_as_lock_file):
        mode='r'
    else:
        assert ((f == CONST.LOCK_FILENAME) and (not use_self_as_lock_file)) or ((CONST.LOCK_FILENAME != f) and (use_self_as_lock_file)), debugmsg("'{f}' '{lf}' '{b}'".format(f=f, lf=CONST.LOCK_FILENAME, b=use_self_as_lock_file))
        raise Exception("wtf coding")
    assert ((not use_self_as_lock_file) and 'x' == mode) or ((use_self_as_lock_file) and ('r' == mode))
    try:
        #retry=False
        while True:
            try:
                retry=False
                lockfile_handle = open(f, mode=mode)
                #a function defined inside a function, ok... it works.
                def lockfileclosure() -> None:
                    if __debug__:
                        debugpr("Closing lockfile '{f}'".format(f=f))
                    lockfile_handle.close()
                    assert lockfile_handle.closed
                    #XXX: ok don't remove it because then we cannot check the lock and thus cannot detect if script is already running!
                    ##attempt to remove the lockfile iff it's not DOLLAR0, doh
                    #if not use_self_as_lock_file and CONST.DOLLAR0 != f:
                    #    #in which case it would be 0 bytes:
                    #    fsize=-1
                    #    try:
                    #        fsize=os.stat(f).st_size
                    #    except FileNotFoundError as e:
                    #        pass
                    #    if -1 == fsize:
                    #        debugpr("lockfile is gone, which most likely means you tried to run, at least once, the script while it was already running")
                    #    elif 0 == fsize:
                    #        if __debug__:
                    #            debugpr("Deleting lockfile '{f}'".format(f=f))
                    #        try:
                    #            os.unlink(f)
                    #        except Exception as e:
                    #            warn("Failed to delete lockfile '{f}', ignoring... {e}".format(f=f, e=e))
                    #            pass
                    #    else:
                    #        warn("Log file '{f}' was not 0 bytes as it should be if we created it! It is '{size}' bytes. Not deleting!".format(f=f, size=fsize))
                    atexit.unregister(lockfileclosure)

                atexit.register(lockfileclosure)
            except FileExistsError:
                #lockfile may exist from before, so we retry one more time and open it in read mode this time. Note: we don't use the existence of the file as indication that this script is already running, but rather the locking LOCK_EX from below, on it.
                #warn("Unclean (script)exit of a prev. run  detected due to already-existing lock file '{f}'".format(f=f)) #this doesn't apply anymore because we're never deleting the lock!
                if __debug__:
                    debugpr("Attempting to use already-existing lock file '{f}' (this is normal)".format(f=f))
                mode='r'
                retry=True
                pass
            #except Exception:
            #    #XXX: any other errors? handle them how ? oh wait I don't need to manually raise here, since it will do the same as 'raise' if it's an exception different than the one I'm already handling above aka FileExistsError
            #    raise

            if not retry:
                break
    except:
        warn("Couldn't open lock file '{f}' in mode='{mode}'".format(f=f, mode=mode))
        if not use_self_as_lock_file and 'x' == mode:  #yes, mode can be 'r' here even tho not using self(aka DOLLAR0) as lock file!
            if not os.access(f, os.W_OK):
                warn("Cannot create/write to file '{f}' and creating it is required! Maybe you don't have permission in that dir(tried user='{user}', effective user id='{eid}')!".format(f=f, user=CONST.USER, eid=os.geteuid()))
        raise
    try:
        fcntl.flock(lockfile_handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        #src: https://stackoverflow.com/questions/2959474/making-a-python-script-only-be-able-to-run-once-at-a-time/7256476#7256476
    except:
        warn("This script({dollar0}) is already running. Cannot start it again.".format(dollar0=CONST.DOLLAR0))
        sys.exit(2) #this runs all of the atexit`s (see the def function with the @atexit.register tag somewhere in this script)!
    if __debug__:
        debugpr("Normal startup(single instance of this script({dollar0}) started)".format(dollar0=CONST.DOLLAR0))

#src: https://stackoverflow.com/questions/2806897/what-is-the-best-way-for-checking-if-the-user-of-a-script-has-root-like-privileg/52621917#52621917
def is_root() -> bool:
    return os.geteuid() == 0

def sanity_checks() -> None:
    assert type(CONST.MINTEMP) is float, debugmsg(type(CONST.MINTEMP))
    assert type(CONST.MAXTEMP) is float, debugmsg(type(CONST.MAXTEMP))
    assert CONST.MINTEMP >= 0, debugmsg(CONST.MINTEMP)
    assert CONST.MINTEMP <= 100, debugmsg(CONST.MINTEMP)
    assert CONST.MAXTEMP >= 0, debugmsg(CONST.MAXTEMP)
    assert CONST.MAXTEMP <= 120, debugmsg(CONST.MAXTEMP)

def ensure_sys_is_rw() -> None:
    is_ro=False
    with open("/proc/mounts", mode='r', buffering=1, closefd=True) as mounts:
        for line in mounts:
            if line.find(" /sys ") >= 0 and any(["ro" == word for word in line.replace(","," ").split(sep=" ")]):
                #src: https://stackoverflow.com/questions/4154961/find-substring-in-string-but-only-if-whole-words/54117781#54117781
                eprint(line.replace(","," ").split(sep=" "))
                is_ro=True
                break

    #try another method:
    if not is_ro:
        #cmd='''
        #mount | grep -F ' /sys ' | grep -w ro
        #'''
        cmd=f"{CONSTOS.MOUNT} | {CONSTOS.GREP} -F -- ' /sys ' | {CONSTOS.GREP} "
        #don't output the found line, if not in debug mode
        if not __debug__:
            cmd+="-q "
        cmd+="-w -- 'ro'"
        #ret = subprocess.run( shlex.split(cmd, comments=False, posix=True), shell=True) #can't pipe
        ret = subprocess.Popen( cmd, shell=True, executable=f"{CONSTOS.SHELL}", stdin=None, stdout=None, stderr=None) #stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #output = ret.communicate()[0]
        #eprint(output)
        if __debug__:
            debugpr("Ran:",ret.args)
        ret.wait()
        if __debug__:
            debugpr("Exitcode:",ret.returncode)
        if 0 == ret.returncode:
            is_ro = True
        elif 1 != ret.returncode:
            warn(f"Some unexpected fail(ec='{ret.returncode}') executing:", ret.args)

    if is_ro:
        eprint("/sys is mounted readonly(eg. you've booted archlinux iso and you're inside arch-chroot)")
        eprint("attempting to remount,rw or else cpupower governor set will fail ...", end='')
        remount_cmd=shlex.split(f"{CONSTOS.MOUNT} /sys -o remount,rw")
        ret = subprocess.Popen( remount_cmd, shell=False, stdin=None, stdout=None, stderr=None)
        if __debug__:
            debugpr("Ran:", ret.args)
        ret.wait()
        if __debug__:
            debugpr("Exitcode:",ret.returncode)
        if 0 != ret.returncode:
            eprint("fail({r})".format(r=ret.returncode))
            warn("Failed to remount,rw /sys")
        else:
            eprint("ok.")

    #now let's be sure it is rw after all the above:
    cmd=f"{CONSTOS.MOUNT} | {CONSTOS.GREP} -F -- ' /sys ' | {CONSTOS.GREP} -w -- 'rw'"
    if __debug__:
        see_stdout=None #aka yes
    else:
        see_stdout=subprocess.DEVNULL #aka don't see
    ret = subprocess.Popen( cmd, shell=True, executable=f"{CONSTOS.SHELL}", stdin=None, stdout=see_stdout, stderr=None)
    if __debug__:
        debugpr("Ran:",ret.args)
    ret.wait()
    if __debug__:
        debugpr("Exitcode:",ret.returncode)
    if 0 != ret.returncode:
        fail(f"/sys is not mounted, or not mounted rw still. exitcode='{ret.returncode}' after executing:", ret.args)

#ie. CPUs are not added/removed at runtime eg. /sys/devices/system/cpu/online doesn't change!
assume_CPUs_state_never_changes:bool=True #FIXME: this should be a const, or maybe not... 

cached_online_CPUs_list: Optional[List[str]]=None
FASTER:bool=True #FIXME: ok, this should be a const.

def signal_handler(sig: signal.Signals, frame: FrameType) -> None:
    eprint('\nYou pressed Ctrl+C! Exiting...')
    sys.exit(128+signal.SIGINT)

#init some wannabe consts
def init() -> None:
    if FASTER:
        assume_CPUs_state_never_changes=True
    else:
        assume_CPUs_state_never_changes=False

    signal.signal(signal.SIGINT, signal_handler) #returns the previous handler aka "<built-in function default_int_handler>", which(as a return) we ignore.

    #eof

def get_list_of_online_CPUs() -> List[str]:
    #done: make a cached version of this where result is stored in global var and if some bool is set that says <assume CPUs state doesn't change> then use the cached version for speed
    global assume_CPUs_state_never_changes
    global cached_online_CPUs_list
    if assume_CPUs_state_never_changes and cached_online_CPUs_list is not None:
        return cached_online_CPUs_list #oh: how to return non-Optional from Optional? oh it just needs a different 'if None != var' like 'if var is not None' instead!
    #format: 2,4-31,32-63
    #done: 'cat' that file:
    ifile="/sys/devices/system/cpu/online"
    with open(ifile, mode='r', buffering=1, closefd=True) as f:
        line = f.readline()

    #line="2,4-31,32-63"
    #line="0-1,3"
    #line="0-3"
    online_CPUs_groups=line.split(',')
    online_CPUs: List[str]=[]
    for each_CPU_group in online_CPUs_groups:
        if '-' in each_CPU_group:
            [minCPU,maxCPU]=each_CPU_group.split('-')
            #63 is value of `cat /sys/devices/system/cpu/kernel_max`, although the values in 'online' can be higher than 'kernel_max'(aka CONFIG_NR_CPUS - 1)
            imin=int(minCPU)
            imax=int(maxCPU)
            assert 0 <= imin <= 63, debugmsg(minCPU)
            assert 0 <= imax <= 63, debugmsg(maxCPU)
            for eachCPU in range(imin, imax + 1, 1): #range is exclusive to the right limit!
                online_CPUs.append(str(eachCPU))
        else:
            online_CPUs.append(each_CPU_group)
    if None == cached_online_CPUs_list:
        cached_online_CPUs_list = online_CPUs
    else:
        assert False == assume_CPUs_state_never_changes
        raise Exception("Shouldn't be reached, yet. That is, the variant where it's already cached but we're recomputing it anyway...")
    return online_CPUs

def unique(list: List[Any]) -> Set[Any]:
    return set(list) #aka `sort -u`

def get_current_cpu_governor() -> str:
    #done: need `sort -u` here:
    squashed_set:Set[Any]=unique(get_current_cpu_governors())
    if len(squashed_set) != 1:
        #done: raise exception only when not all CPUs use the same governor
        raise Exception("CPUs have different governors: ", squashed_set)
        #TODO: handle this better?
    #return squashed_set.pop() #error: Returning Any from function declared to return "str"
    return str(squashed_set.pop())

#TODO FIXME: online/offline state of CPUs are ignored in other parts of the code (ie. the code that keeps some files open like the setspeed code! so I guess I should maybe fix that

def get_current_cpu_governors() -> List[str]:
    governors_of_each_CPU: List[str] = []
    for each_CPU in get_list_of_online_CPUs():
        pfile=f"/sys/devices/system/cpu/cpufreq/policy{each_CPU}/scaling_governor"
        with open(pfile, mode='r', buffering=1, closefd=True) as f:
            governor = f.readline().strip()
            assert governor.islower(), debugmsg(governor)
            governors_of_each_CPU.append(governor)
    #governors_of_each_CPU.append("test")
    return governors_of_each_CPU

#returns True if used fallback method
def set_cpu_governor(gov: str, use_fallback_method:bool=False) -> bool:
    gov=gov.strip().lower()
    #done: use /sys/devices/system/cpu/cpufreq/policy0/scaling_governor to set governor, fallback to cpupower if that fails!
    #no, not here: set min/max freqs here? --min 800MHz --max 1400MHz
    if not use_fallback_method:
        for each_CPU in get_list_of_online_CPUs():
            gfile = f"/sys/devices/system/cpu/cpufreq/policy{each_CPU}/scaling_governor"
            to_write:str = gov
            with open(gfile, mode="w", buffering=1, closefd=True) as f:
                if __debug__:
                    l=len(to_write)
                    bytes_written = f.write(to_write) #this must exist
                    assert l == bytes_written, debugmsg(l, bytes_written, to_write)
                else:
                    f.write(to_write) #this must exist
        return False
    else: #must use fallback method
        qgov=shlex.quote(gov)
        cmd=shlex.split(f"{CONSTOS.CPUPOWER} --cpu all frequency-set --related --governor {qgov}")
        ret = subprocess.Popen( cmd, shell=False, stdin=None, stdout=None, stderr=None)
        if __debug__:
            debugpr("Ran:",ret.args)
        ret.wait()
        if __debug__:
            debugpr("Exitcode:",ret.returncode)
        if 0 != ret.returncode:
            fail(f"Couldn't set governor '{gov}'(quoted:{qgov}). Exitcode='{ret.returncode}' after executing:", ret.args)
        return True

#doneTODO: get min/max and all intermediary speeds that can be set, from /sys/devices/system/cpu/cpufreq/policy*/scaling_available_governors  (well, NOT from that file, hey!) which has a line like: "1400000 1300000 1200000 1100000 1000000 900000 800000 " (with that extra space at the end!)

#returns True if used fallback method
def set_cpu_min_max_limits(min:int, max:int, use_fallback_method:bool=False) -> bool:
    #doneTODO: also use fallback method ie. cpupower --cpu all frequency-set --related --governor userspace --min 800MHz --max 1400MHz
    assert Z575.KNOWN_MIN_SPEED <= min <= Z575.KNOWN_MAX_SPEED, debugmsg(Z575.KNOWN_MIN_SPEED, min, Z575.KNOWN_MAX_SPEED)
    assert Z575.KNOWN_MIN_SPEED <= max <= Z575.KNOWN_MAX_SPEED, debugmsg(Z575.KNOWN_MIN_SPEED, max, Z575.KNOWN_MAX_SPEED)
    #TODO: how to declare a read-only aka const var here?
    min_speed_limit:str = str(min)
    max_speed_limit:str = str(max)
    if not use_fallback_method:
        for each_CPU in get_list_of_online_CPUs():
            minfile = f'/sys/devices/system/cpu/cpufreq/policy{each_CPU}/scaling_min_freq'
            maxfile = f'/sys/devices/system/cpu/cpufreq/policy{each_CPU}/scaling_max_freq'
            #TODO: fix the code duplication here
            to_write:str
            #TODO: should probably read-back to ensure the new value stuck.
            to_write = min_speed_limit
            with open(minfile, mode="w", buffering=1, closefd=True) as f:
                if __debug__:
                    l=len(to_write)
                    bytes_written = f.write(to_write)
                    assert l == bytes_written, debugmsg(l, bytes_written, to_write)
                else:
                    f.write(to_write)
            to_write = max_speed_limit
            with open(maxfile, mode="w", buffering=1, closefd=True) as f:
                if __debug__:
                    l=len(to_write)
                    bytes_written = f.write(to_write)
                    assert l == bytes_written, debugmsg(l, bytes_written, to_write)
                else:
                    f.write(to_write)
            #XXX: it auto-closes thus flush/sync when the 'with' block ends! keep this in mind when you later want to seek(0) and re-read, maybe it won't work unless a f.flush() or a f.write(newline) is done first? unsure.
        return False
    else: #must use fallback method
        cmd=shlex.split(f"{CONSTOS.CPUPOWER} --cpu all frequency-set --related --min {min_speed_limit} --max {max_speed_limit}")
        ret = subprocess.Popen( cmd, shell=False, stdin=None, stdout=None, stderr=None)
        if __debug__:
            debugpr("Ran:",ret.args)
        ret.wait()
        if __debug__:
            debugpr("Exitcode:",ret.returncode)
        if 0 != ret.returncode:
            fail(f"Couldn't set min/max speed limits: {min_speed_limit}/{max_speed_limit}. Exitcode='{ret.returncode}' after executing:", ret.args)
        return True

def get_current_speed_limit(min:bool) -> int:
    #done: need `sort -u` here:
    squashed_set:Set[Any]=unique(get_current_speed_limit_for_all_CPUs(min))
    if len(squashed_set) != 1:
        #done: raise exception only when not all CPUs use the same governor
        raise Exception("CPUs have different speed limits: ", squashed_set)
        #TODO: handle this better?
    #return squashed_set.pop() #error: Returning Any from function declared to return "str"
    #ret_str:str =squashed_set.pop()
    #doneFIXME: ^ the type of ret_str although declared 'str' becomes 'int', how in teh?!!
    ret_str:str = str(squashed_set.pop())
    ret = int(ret_str)
    str_of_ret:str = str(ret)
    #python compare strings in python: well, this works except when they are of different type eg. str vs int
    assert str_of_ret == ret_str, debugmsg(f"'{ret}' != '{ret_str}' != '{str_of_ret}'; types: {type(ret)} != {type(ret_str)} != {type(str_of_ret)}")
    return ret

#TODO FIXME: online/offline state of CPUs are ignored in other parts of the code (ie. the code that keeps some files open like the setspeed code! so I guess I should maybe fix that

#Can return one of min or max speed limits of all the online CPUs, eg. seen as: "current policy: frequency should be within 'min' MHz and 'max' MHz." when using 'cpupower'
def get_current_speed_limit_for_all_CPUs(min:bool) -> List[int]:
    if min:
        file_part_name="scaling_min_freq"
    else:
        #it's max:
        file_part_name="scaling_max_freq"
    speed_limits_of_each_CPU: List[int] = []
    for each_CPU in get_list_of_online_CPUs():
        pfile=f"/sys/devices/system/cpu/cpufreq/policy{each_CPU}/{file_part_name}"
        with open(pfile, mode='r', buffering=1, closefd=True) as f:
            speed_limit_str = f.readline().strip()
            speed_limit_int:int = int(speed_limit_str)
            assert Z575.KNOWN_MIN_SPEED <= speed_limit_int <= Z575.KNOWN_MAX_SPEED, debugmsg(Z575.KNOWN_MIN_SPEED, speed_limit_int, speed_limit_str, Z575.KNOWN_MAX_SPEED)
            speed_limits_of_each_CPU.append(speed_limit_int)
    return speed_limits_of_each_CPU

def ensure_cpu_min_max_limits_are_set() -> None:
    #TODO: test what happens (should throw for now) when cores have different speed limits! and then handle the case, or don't throw!
    min_limit_now:int =get_current_speed_limit(True) #aka min speed
    max_limit_now:int =get_current_speed_limit(False) #aka max speed
    min_speed_limit_to_set:int = Z575.KNOWN_MIN_SPEED
    max_speed_limit_to_set:int = Z575.KNOWN_MAX_SPEED
    assert Z575.KNOWN_MIN_SPEED <= min_limit_now <= Z575.KNOWN_MAX_SPEED, debugmsg(Z575.KNOWN_MIN_SPEED, min_limit_now, Z575.KNOWN_MAX_SPEED)
    assert Z575.KNOWN_MIN_SPEED <= max_limit_now <= Z575.KNOWN_MAX_SPEED, debugmsg(Z575.KNOWN_MIN_SPEED, max_limit_now, Z575.KNOWN_MAX_SPEED)
    if min_limit_now == min_speed_limit_to_set and max_limit_now == max_speed_limit_to_set:
        if __debug__:
            debugpr(f"Already set min/max to {min_speed_limit_to_set}/{max_speed_limit_to_set}. Doing nothing about it.")
        return
    used_fallback:bool = set_cpu_min_max_limits(min=min_speed_limit_to_set, max=max_speed_limit_to_set, use_fallback_method=False)
    assert False == used_fallback, debugmsg(used_fallback)
    try:
        min_limit_now=get_current_speed_limit(True) #aka min speed
        max_limit_now=get_current_speed_limit(False) #aka max speed
        if min_limit_now == min_speed_limit_to_set and max_limit_now == max_speed_limit_to_set:
            if __debug__:
                debugpr(f"Successfully set min/max to {min_speed_limit_to_set}/{max_speed_limit_to_set} using normal method(ie. not fallback).")
            return
    except:
        pass
    warn(f"Couldn't set min/max speed limits {min_speed_limit_to_set}/{max_speed_limit_to_set} (it's now {min_limit_now}/{max_limit_now}). Retrying using fallback method aka 'cpupower'...")
    used_fallback = set_cpu_min_max_limits(min=min_speed_limit_to_set, max=max_speed_limit_to_set, use_fallback_method=True)
    assert True == used_fallback, debugmsg(used_fallback)

    min_limit_now=get_current_speed_limit(True) #aka min speed
    max_limit_now=get_current_speed_limit(False) #aka max speed
    if min_limit_now == min_speed_limit_to_set and max_limit_now == max_speed_limit_to_set:
        if __debug__:
            debugpr(f"Successfully set min/max to {min_speed_limit_to_set}/{max_speed_limit_to_set} using fallback method(ie. second try).")
        return
    fail(f"Couldn't set min/max speed limits {min_speed_limit_to_set}/{max_speed_limit_to_set} (it's now {min_limit_now}/{max_limit_now}). Even after retrying with fallback method aka 'cpupower'.")

#TODO: learn how to do python docs
#returns the previous governor, or 'undetermined' if getting current governor failed
def ensure_cpu_governor_is(gov: str) -> str:
    gov=gov.strip().lower()
    bad_gov=False
    cur_gov='undetermined'
    try:
        cur_gov = get_current_cpu_governor()
    except:
        bad_gov=True
        pass
    if not bad_gov:
        bad_gov=(gov != cur_gov)

    if bad_gov:
        used_fallback=set_cpu_governor(gov, False)
    else:
        used_fallback=False

    try:
        now_gov = get_current_cpu_governor()
        if now_gov != gov and not used_fallback:
            warn(f"Couldn't set governor '{gov}'(it's now '{now_gov}'). Retrying using fallback method aka 'cpupower'...")
            #retry with fallback method:
            uf2ndtime=set_cpu_governor(gov, True)
            assert True == uf2ndtime, debugmsg("bad coding")
            now_gov = get_current_cpu_governor()
        if now_gov != gov:
            if used_fallback:
                m=1
            else:
                m=2
            fail(f"Couldn't set governor '{gov}'(prev. gov. was:'{cur_gov}'). It should've been set though!(gov='now_gov' after trying to set it) Tried {m} methods.")
    except:
        #if it excepts we allow it, note that fail() will also except aka raise!
        raise
    return cur_gov


def set_prio() -> None:
    wanted_prio=-19 #not quite -20
    new_prio=renice(wanted_prio)
    assert new_prio == wanted_prio, failmsg(f"Tried renice({wanted_prio}) but remained at only renice({new_prio})")

def renice(wanted_prio:int, show_err:bool=True) -> int:
    assert -20 <= wanted_prio <= 19, debugmsg(wanted_prio)
    #from 'man renice':
    #The  superuser may alter the priority of any process and set the prior‐
    #ity to any value in the range -20 to 19.   Useful  priorities  are:  19
    #(the  affected  processes will run only when nothing else in the system
    #wants to), 0 (the ``base'' scheduling priority), anything negative  (to
    #make things go very fast).

    cur_prio=os.nice(0)
    #new_prio=os.nice(wanted_prio)
    #print("1st try:", new_prio)
    if cur_prio != wanted_prio:
        err=None
        try:
            cur_prio=os.nice(wanted_prio - cur_prio)
        #except PermissionError as pe:
        except Exception as e:
            #eprint(pe)
            err=e
            pass
        #print("2nd try:", new_prio)
        if cur_prio != wanted_prio and show_err:
            warn(f"Failed({err}) to renice({wanted_prio}), now at renice({cur_prio})")
    return cur_prio


def add_hook_to_set_safespeeds_onexit() -> None:
    atexit.register(atexit_hook_set_lowest_speed)
    #eof

#don't actually call this directly to set lowest speed; it's meant for only 2 call cases!
def atexit_hook_set_lowest_speed() -> None:
    lowest_speed=Z575.KNOWN_MIN_SPEED #FIXME: should I use the set min/max within the governor (so to speak) ? or the hardcoded known min/max ? if the latter this means I'd have to hardcode them for each host and thus each host must be known beforehand.
    if __debug__:
        debugpr("Safely setting to lowest speed ({ls} Khz)...".format(ls=lowest_speed))
    ensure_sys_is_rw()
    ensure_cpu_governor_is("userspace")
    ensure_cpu_min_max_limits_are_set() #just making sure lowest speed is set as the min limit, else it will fail to set it. eg. if --min speed was 1400000 but you want 800000, it will fail to set!
    #doneTODO: set speed to lowest here!
    ret=set_current_speed(lowest_speed)
    if ret is None or ret != lowest_speed:
        #try one more time after a short pause
        time.sleep(CONST.SLEEPTIME_MOST)
        set_current_speed(lowest_speed)
    atexit.unregister(atexit_hook_set_lowest_speed)
    #eof

def update_window_title(sleeptime:float) -> None:
    set_xwindow_title(PROGRAM.NAME + " v"+PROGRAM.VERSION + " - ensures max temperature stays between ({min}..{max}) checks every {sleeptime} seconds.".format(min=CONST.MINTEMP, max=CONST.MAXTEMP, sleeptime=sleeptime))

def main() -> int:

    sanity_checks()
    init()
    #set_prio() #this call was here only for testing

    #src: https://stackoverflow.com/questions/22574201/running-python-script-as-root/22574300#22574300
    if not is_root():
        sys.exit("Only root can run this script (you're '{whoami}')".format(whoami=os.getlogin()))
    #TODO: add elevate from grubmero.py

    #XXX: Can't ensure_* before root-check, because then we can't create lock file due to missing permissions for the non-root user in /var/run/
    ensure_not_already_running()

    set_prio()
    if __debug__: #yes, twice
        set_prio()

    #update_window_title(CONST.SLEEPTIME)
    print(PROGRAM.NAME + " v"+PROGRAM.VERSION + " - Varies CPU speed to ensure max temperature stays between ({min}..{max}). Checks every {sleeptime} seconds(min={mst}, max={xst} where max is reached after {safe_seconds} sec of below {min} C temperature).".format(min=CONST.MINTEMP, max=CONST.MAXTEMP, sleeptime=CONST.SLEEPTIME, mst=CONST.SLEEPTIME_LEAST,xst=CONST.SLEEPTIME_MOST, safe_seconds=CONST.INCREASE_SLEEPTIME_AFTER_X_SECONDS_OF_CONSTANT_UNDER_MINTEMP))

    #TODO: these two should probably be part of the loop, or maybe only run them if the setting of the speed fails?! so run this then retry once.
    ensure_sys_is_rw()
    prev_gov=ensure_cpu_governor_is("userspace")
    debugpr("Previous CPU governor:", prev_gov)
    #okTODO: set min/max freqs here --min 800MHz --max 1400MHz
    ensure_cpu_min_max_limits_are_set()
    #TODO: probably need to ensure the governor remains userspace while $0 is running, but how often should we check? as often as screen updates? ie. CONST.SLEEPTIME  , or only when setting speeds fails! that's right, do this!


    #TODO: disable boost by echo-ing 0 (as root) into /sys/devices/system/cpu/cpufreq/boost  but this command still says "yes": cpupower frequency-info|grep -i "Active:"   However, technically this doesn't matter because boost aka P0 is the same as P1 in terms of voltage and frequency via 3150_kernel_undervolting.patch
    with open("/sys/devices/system/cpu/cpufreq/boost", mode="w+", buffering=1, closefd=True) as f:
        prev=f.readline().strip()
        assert prev.isdigit(), debugmsg(prev)
        if __debug__:
            if int(prev) != 0:
                debugpr("Disabling CPU boost (was enabled)")
            else:
                debugpr("re-Disabling CPU boost (but was already disabled)")
        f.seek(0)
        f.write("0") #turn off CPU 'boost' ie. don't auto-jump(via hardware) to 2.9Ghz if temperature is below 65C
        f.flush()
        f.seek(0)
        readback:str=f.readline().strip()
        readback_int=int(readback)
        assert readback_int == 0, debugmsg(readback)

    #TODO: actual KHz speed(seen correctly even when overclocked) eg. 2587581 KHz is in /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq
    #XXX: current set CPU speed(doesn't see the real/overclocking speed) eg. 1400000 KHz

    open_tfiles()
    open_speedfiles()

    #doneTODO: add break handler which will set max CPU speed to lowest, or actually, also set it to lowest atexit! take from grubmero.py
    add_hook_to_set_safespeeds_onexit() #when C-c is pressed, cpu speed will be set to minimum! XXX: has to be ran after opening files, so to ensure they aren't closed first

    #TODO: use colors instead of writing the CPU speed when switching, and so you can write only one char, colored. Maybe only write the speeds once, with the same color, at the beginning. Make this dependent on the global const var FASTER

    #debugpr("Max:",get_temperatur()) #yeFIXME: this is temporary
    #debugpr("Current speed:", get_current_speed())

    #loop start:
    #ahaTODO: loop here
    #TODO: integrate this hack
    with open("/sys/devices/system/cpu/cpufreq/policy0/scaling_available_frequencies", mode="r", buffering=1, closefd=True) as af_file:
        line=af_file.readline() #ie. "1400000 1300000 1200000 1100000 1000000 900000 800000 " (with the space at the end)
        available_frequencies: List[int] = list(map(int,line.strip().split(sep=" "))) #note: strip is trim; type List[int] is needed to ensure each element is int so the sort will be numeric rather than string; and ofc to accomplish that list(map(int, ...)) was needed! thx to https://www.askpython.com/python/string/convert-string-to-list-in-python
        assert len(available_frequencies) == 7, debugmsg(available_frequencies)
        available_frequencies.sort()
        if __debug__:
            debugpr(available_frequencies)
    #af_file.close()
    #available_frequencies=
    cols_now=0
    highest_speed=Z575.KNOWN_MAX_SPEED
    lowest_speed=Z575.KNOWN_MIN_SPEED
    max_index=len(available_frequencies) - 1

    #global so we can access it from exit handler
    global max_seen_temp
    #setting a non-None value so I won't have to always check for None inside the while-loop!
    max_seen_temp=0
    global min_seen_temp
    min_seen_temp=120
    #TODO: properly define/set colors ie. by running 'tput' ?
    #color_red="\x1B[41m" #tput setab 1
    #color_green="\x1B[42m" #tput setab 2
    #color_darkred="\x1B[48;5;52m" #tput setab 52
    #color_reset="\x1B(B\x1B[m" #tput sgr0, in xfce4-terminal, TERM=xterm-256color
    temp_now: int = 257
    prev_temp = 255 #marker
    sleep_time = CONST.SLEEPTIME
    prev_sleep_time:float =0 #so it will cause a title update
    time_spent_below_mintemp:float = 0
    while True:
        speed_now = get_current_speed()
        if speed_now is None:
            print("?", end="")
            set_current_speed(lowest_speed)
            time.sleep(sleep_time)
            continue
        if prev_temp != 255:
            #ie. this means temp_now was already set! so this is second+ run.
            prev_temp=temp_now
        temp_now = math.ceil(get_temperatur()) #rounded up
        if prev_temp == 255:
            #set to same, for the first time run
            prev_temp = temp_now
        if temp_now > max_seen_temp:
            max_seen_temp = temp_now
            print(">max_seen_temp={red}{t}{reset}C".format(t=max_seen_temp, red=bcolors.BG_RED, reset=bcolors.RESET), end="")
        if temp_now < min_seen_temp:
            min_seen_temp = temp_now
            #print(f"<min_seen_temp={colored(bcolors.BG_GREEN,str(min_seen_temp))}C", end="")
            print("<min_seen_temp={green}{t}{reset}C".format(t=min_seen_temp, green=bcolors.BG_GREEN, reset=bcolors.RESET), end="")

        #print("{speed_now}/{temp_now} ".format(speed_now=speed_now, temp_now=temp_now), end="")
        if temp_now >= CONST.MAXTEMP:
            next_speed=lowest_speed
            if prev_temp < CONST.MINTEMP and temp_now > CONST.MAXTEMP:
                sleep_time = CONST.SLEEPTIME_LEAST
                #update_window_title(sleep_time)
                time_spent_below_mintemp=0
                #diff_temp = temp_now - prev_temp
                print(">jumpovertemp={darkred}[{then}-{now}]{reset}C".format(then=prev_temp, now=temp_now, darkred=bcolors.BG_DARKRED, reset=bcolors.RESET), end="")

        elif temp_now <= CONST.MINTEMP:
            if time_spent_below_mintemp >= CONST.INCREASE_SLEEPTIME_AFTER_X_SECONDS_OF_CONSTANT_UNDER_MINTEMP:
                sleep_time = CONST.SLEEPTIME_MOST
                #update_window_title(sleep_time)
            time_spent_below_mintemp += sleep_time
            next_speed_index=available_frequencies.index(speed_now)
            assert 0 <= next_speed_index <= max_index, debugmsg(next_speed_index)
            if next_speed_index < max_index:
                next_speed_index+=1
            #cap it:
            if __debug__:  #under debug since this shouldn't normally happen!
                if next_speed_index > max_index:
                    warn(f"next_speed_index was {next_speed_index} > max_index aka {max_index}, this shouldn't happen!")
                    next_speed_index = max_index
                elif next_speed_index < 0:
                    warn(f"next_speed_index was {next_speed_index} < 0, this shouldn't happen!")
                    next_speed_index = 0
            assert 0 <= next_speed_index <= max_index, debugmsg(next_speed_index)
            next_speed = available_frequencies[next_speed_index]
            assert available_frequencies.index(next_speed) >= 0, debugmsg("impossible")

        if next_speed != speed_now:
            set_current_speed(next_speed)
            if next_speed > speed_now:
                c=">"
            else:
                c="<"
            print("{c}{spd}".format(c=c, spd=next_speed), end="")
        else:
            #if next_speed == lowest_speed:
            #    print("[", end="")
            if next_speed == highest_speed:
                print("]", end="")
            else:
                print(".", end="")

        cols_now+=1
        sys.stdout.flush()
        if cols_now >= CONST.MAXLINELENGTH:
            print()
            cols_now=0
        if prev_sleep_time != sleep_time:
            update_window_title(sleep_time)
            if prev_sleep_time < sleep_time:
                c=">"
            else:
                c="<"
            print("{c}u=[{pst} to {st}]sec".format(c=c, pst=prev_sleep_time, st=sleep_time))
        time.sleep(sleep_time)
        prev_sleep_time = sleep_time
    #loop end:

    #TODO: should I even bother calling these manually here? shouldn't I just allow for them to run on exit?
    atexit_hook_set_lowest_speed() #run it here so that it won't be invoked atexit ! which would fail due to some of the closed files below (the setspeed ones)
    close_speedfiles()
    close_tfiles()

    if __debug__:
        debugpr("Normal exit")
    return 0

if __name__ == '__main__':
    if __debug__:
        debugpr("Running main()")
    main()
else:
    if __debug__:
        debugpr("Imported '{self}' as module.".format(self=CONST.DOLLAR0))

#Keep this last:
#vim filetype is set to python below, otherwise vim will use tabs instead of spaces for indentation when pypy3 is interpreter
# vim: set ft=python
