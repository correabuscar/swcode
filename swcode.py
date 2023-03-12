#!/usr/bin/pypy3 -bb
#src: https://docs.python.org/3/tutorial/modules.html

#this is swcode module, located at /swcode/swcode.py supposedly.

#XXX: source like this:
#----
#import sys
#oldsyspath=sys.path
#sys.path.append("/swcode/")
#import swcode
#sys.path=oldsyspath
#----
#
#this is so that it works under any other user, instead of setting PYTHONPATH for all, including for 'sudo' somehow.
#the oldsyspath restoration is optional!
#to allow 'mypy' to run without error-ing, you will need to set this(unless you're already in cwd=/swcode, ofc):
#export MYPYPATH="$MYPYPATH:/swcode/"


#---------- this block is to make read-only constants (they can still be overridden, because python) but only if you really intend to.
##so, apparently this can be changed!
#import enum
#class Module(enum.Enum):
#   #__version__ = "0.0.1"
#   VERSION = "0.0.1"
#   VERSION2 = "0.0.1"
#   VERSION3 = VERSION2

#XXX: using underscore prefix so that 'from swcode import *' (which is discouraged) won't import these too.

#src: https://stackoverflow.com/questions/100003/what-are-metaclasses-in-python/35732111#35732111
class _ROValidator(type):  # a metaclass!
    #def __new__(metacls, cls, bases, clsdict):
    #    metacls.__slots__=()
    #    return super().__new__(metacls, cls, bases, clsdict)
    #__setattr__ src: https://stackoverflow.com/questions/100003/what-are-metaclasses-in-python/21999253#21999253
    def __setattr__(self, name:str, value:str) -> None:
        #print(type(cls), type(name), type(value))
        raise AttributeError(f"Won't set read-only constant '{name}' of class '{self}' to value '{value}'")
    def __delattr__(self, name:str) -> None:
        #print(type(name))
        #detects deletion of the class who has self as metaclass, not deletions of attributes within this metaclass.
        raise AttributeError(f"1Attempted to delete attribute '{name}' of class '{self}', perhaps in order to defeat read-only-ness of constants?")

#__slots__ src: https://stackoverflow.com/questions/2682745/how-do-i-create-a-constant-in-python/23274028#23274028
#class _Module(object):
class Constants(metaclass=_ROValidator):
#class _Module(metaclass=_ROValidator):
    __slots__ = () #this makes inst.VERSION="2" yield: AttributeError: '_Module' object attribute 'VERSION' is read-only
    #VERSION=ValidateType("0.0.8")
    #VERSION="0.0.10"
    # ^ this is swcode module's version
    #def __init__(self):
    #    a=super().__init__()
    #    self.__slots__=()
    #    return a
    #    #del self.__dict__
    #    #del self.__weakref__
    #def __dir__(self):
    #    a = super().__dir__()
    #    a.remove("__slots__")
    #    a.remove("__dict__")
    #    #no effect
    #    return a
    def __init_subclass__(cls) -> None:#, /, **kwargs):
        #if hasattr(cls,'__dict__'): #always true hmm
        #if cls.__dict__: #same
        #print(cls.__dir__)
        if "__dict__" in dir(cls): #good!
            raise SyntaxError(f"failed! __dict__ shouldn't exist! Make sure you add the following line to your subclass(which is '{cls}'): '__slots__ = ()' (there's no way to inherit it or similar, so you must add it by hand)")
        super().__init_subclass__()
        return #apparently doesn't return any value, see: https://docs.python.org/3/reference/datamodel.html#object.__init_subclass__
    def __delattr__(self, name:str) -> None:
        raise AttributeError(f"2Attempted to delete attribute '{name}' of class '{self}', perhaps in order to defeat read-only-ness of constants?")

#nvmTODO: doesn't work
#class _Module(Constants, metaclass=_ROValidator):
class _Module(Constants):
    __slots__ = () #XXX this is required! or it won't detect this: inst.VERSION="2"  TODO: how to not require this in the subclass here?! for now, we'll just except if you forget this! good enough.
    VERSION="0.0.12"
    # ^ this is swcode module's version
    #def __init__(self): #no effect!
    #    self.__slots__=()

if __debug__:
    good=False
    try:
        _Module.VERSION="1" #XXX this works and overrides the value, unless using metaclass=ROValidator with overridden __setattr__! #doneTODO: detect & prevent this from working; maybe needs metaclass? see: https://stackoverflow.com/questions/100003/what-are-metaclasses-in-python/35732111#35732111
    except AttributeError as e:
        good=True
    except Exception as e:
        print(f"Unexpected exception '{type(e)}: {e}'")
        pass
    assert good, "failed to detect assignment of constant, applied to class"

if __debug__:
    good=False
    try:
        del _Module.__setattr__
    except AttributeError as e:
        good=True
    except Exception as e:
        print(f"Unexpected exception '{type(e)}: {e}'")
        pass
    assert good, "failed to detect attribute deletion within the class"


#print(type(_Module.VERSION)) # <class 'str'>
#print(_Module.VERSION) # <class 'str'>
module=_Module() #hmm, so I'm supposed to use the instance?! hmmm, ok. swcode.module.VERSION it is then.
del _Module #so now I can use 'module' instead! mypy however won't complain if I use '_Module' but it will fail at runtime
#^ note that type(inst) will still get this class! even from caller/outside_of_module, and by that logic, can most likely also get the metaclass of it and thus del metaclass.__setattr__ which I could hook but then the metaclass of that metaclass would suffer from the same issue... so just handling these cases is good enough for these readonly-constants implementation attempt.

#print(_Module) #NameError: name '_Module' is not defined
if __debug__:
    good=False
    try:
        module.VERSION="2" #AttributeError: '_Module' object attribute 'VERSION' is read-only
    except AttributeError as e:
        good=True
    except Exception as e:
        print(f"Unexpected exception '{type(e)}: {e}'")
        pass
    assert good, "failed to detect assignment of constant, applied to instance"

if __debug__:
    good=False
    try:
        #can still access class even though it was deleted via type(inst) aka the _habnabit method:
        type(module).VERSION='3'
    except AttributeError as e:
        good=True
    except Exception as e:
        print(f"Unexpected exception '{type(e)}: {e}'")
        pass
    assert good, "failed to detect assignment of constant, applied to class via type(instance)"

if __debug__:
    good=False
    try:
        del module.__setattr__
    except AttributeError as e:
        good=True
    except Exception as e:
        print(f"Unexpected exception '{type(e)}: {e}'")
        pass
    assert good, "failed to detect attribute deletion within the instance"
#----------


#XXX: Within a module, the module’s name (as a string) is available as the value of the global variable __name__
if __name__ == "__main__":
    import os
    full=os.path.realpath(__file__)
    justfname=os.path.basename(full)
    modulename=os.path.splitext(justfname)[0]
    #print(os.path.splitext(full))
    print(f"You attempted to execute python module {justfname} (aka {full}) v{module.VERSION} directly, use 'import {modulename}' instead.")
else:
    #print(f"hello from import-time of module '{__name__}' v{module.VERSION}")
    pass


import sys
import os
from typing import Any, Optional
import errno


#from cuspctrl:
def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)

#src: https://github.com/barneygale/elevate/blob/master/elevate/posix.py
#elevate aka rerunasroot or re-run as root
#Usage: elevate(__file__)  #just like that
def elevate(pass__file__here:str, graphical:bool=False) -> None:
    assert __file__ != pass__file__here, f"{__file__} vs {pass__file__here}"
    assert pass__file__here != "", f"'{pass__file__here}'"
    #XXX: not using "strip()" in case the filename somehow contains spaces as part of its name.
    if __debug__:
        arg0=sys.argv[0]
        if pass__file__here != arg0:
            eprint(f"Found an edge case where: arg0='{arg0}' differs from the passed __file__='{pass__file__here}'")
    if os.geteuid() == 0:
        return

    #done: is shlex.quote() needed for sys.argv values? I guess not because it's an array of args so you know where they each start/end, AND it's not using subshell!

    #not good enough to run the "./a.py" arg!
    #args = [sys.executable] + sys.argv
    #but this is:
    args = [sys.executable]
    args.append(os.path.realpath(pass__file__here))
    args+=sys.argv[1:]
    eprint("Will execute as root:",args)
    commands = []

    #FIXME: if graphical, need to preserve env. vars $DISPLAY and $XAUTHORITY (at least), else it won't start! and pkexec clears them also!  it works fine with 'sudo' though!
    if graphical:
        if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
            commands.append(["pkexec"] + args)
            commands.append(["gksudo"] + args)
            commands.append(["kdesudo"] + args)

    #with 'sudo', under X, will get this output: "QStandardPaths: XDG_RUNTIME_DIR not set, defaulting to '/tmp/runtime-root'"
    commands.append(["sudo"] + args)

    #this 'args' shadows the prev. 'args' inside the 'for'
    for args in commands:
        try:
            os.execlp(args[0], *args)
        except OSError as e:
            # errno.ENOENT aka FileNotFoundError src: https://docs.python.org/3/library/exceptions.html#FileNotFoundError
            #or, last command attempted, then rethrow exception
            if e.errno != errno.ENOENT or args[0] == "sudo":
                raise

#well, I'm being forced to use types when checking via 'mypy --strict "./$0"'
def is_string_empty_or_whitespace(s:Optional[str]) -> bool:
    return s is None or s.strip() == ""
    #it works with "is not" instead of "!=", thanks to papna, LordRyan, aghast, deltab on #python freenode irc!

#def is_string_empty_or_whitespace(s:str) -> bool:
#    return s.strip()==""
#
#def is_string_empty_or_whitespace(s:Optional[Any]) -> bool:
#    return None is s

#def is_empty_env_var(s:str) -> bool:
#    if __debug__:
#        #src: https://stackoverflow.com/questions/8270092/remove-all-whitespace-in-a-string/28607213#28607213
#        import re
#        no_ws = re.sub(r"\s+", "", s, flags=re.UNICODE)
#        assert s == no_ws, f"env.var. name '{s}' has spaces! ie. bad coding somewhere!"
#    #key=s.strip()
#    val=os.environ.get(s)
#    assert type(val) in [str, type(None)], type(s)
#    assert type(val) == type(None), type(val)
#    return None == val or val.strip()==""

def is_X() -> bool:
    disp:Optional[str]=os.environ.get("DISPLAY")
    return not is_string_empty_or_whitespace(disp)


