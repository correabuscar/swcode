#!/bin/bash
#revision 3
#Thu Jun 10 01:20:41 AM CEST 2021

#XXX to be sourced like:
#source /swcode/swcode.bash

if test "0${__swcode_bash_already_sourced}" -ne "0"; then
  #don't re-source if already sourced
  # If not running interactively(ie. bash --login), don't print anything
  #[[ $- == *i* ]] && echo "not re-sourcing already-sourced '$0 $*' aka '${BASH_SOURCE[*]}'" >&2
  #^ "$0" is "-su" above!
  [[ $- == *i* ]] && echo "!!! not re-sourcing already-sourced script '${BASH_SOURCE[*]}'" >&2
  return 0
fi
__swcode_bash_already_sourced=1
export -n __swcode_bash_already_sourced  #-n remove the export property from each NAME
#ie. ^ don't export this! because running scripts within scripts that both source this is valid and both should source it!

#--user defined vars:
z575hostname="Z575"
intelhostname="i87k"
t400hostname="t400"

mainreponame="q1q"
#^ that is /home/user/${mainreponame}  dir or dirsymlink
export mainreponame #XXX at least ~/.second.bashrc uses this!

#-- nothing to change below:
cpu_cores="$(grep -F 'cpu cores' -- /proc/cpuinfo |cut -f2 -d':'|tr -d ' '|head -1)"
#shellcheck disable=SC2034
cpu_cores_minus_1="$(( cpu_cores - 1 ))"

hostname="$HOSTNAME"
if test -z "$hostname"; then
  hostname="$(hostname)"
fi
if test -z "$hostname"; then
  echo "!! Hostname is empty" >&2
  exit 1
fi
export hostname #XXX so it can be used inside rsank.lst(not currently used there), AND inside genericupdateTOfrombasedir script, for renaming host-specific files!

#--- functions:
is_z575() {
  #if test "$HOSTNAME" == "$z575hostname" -o "$(hostname)" == "$z575hostname"; then
  if test  "$hostname" == "$z575hostname"; then
  #XXX: the first test will fail on 'POSIX sh' because HOSTNAME is undefined, thanks shellcheck
    return 0 # ie. hits 'yes' in: if is_z575; then echo 'yes'; else echo 'no'; fi
  else
    return 1 #this will hit 'if ! is_z575; then' or, the 'else' branch of 'if is_z575; then'
  fi
}

is_Z575() {
    is_z575 "$@"
    #  return "$?" #implied, thus not needed
}

is_i87k() {
  #if test "$HOSTNAME" == "$intelhostname" -o "$(hostname)" == "$intelhostname"; then
  if test "$hostname" == "$intelhostname"; then
    return 0
  else
    return 1
  fi
}

is_intel() {
  is_i87k; return "$?"
}

is_t400() {
  #if test "$HOSTNAME" == "$t400hostname" -o "$(hostname)" == "$t400hostname"; then
  if test "$hostname" == "$t400hostname"; then
    return 0
  else
    return 1
  fi
}


if ! is_i87k; then
  if ! is_z575; then
    if ! is_t400; then
      echo "$(tput setab 1)WARNING: none of: intel, Z575 or T400!$(tput sgr0)"
    fi
  fi
fi

#id must not contain "-" else invalid when /bin/sh (guessing it was 'sh') but it did work in just 'bash'
set_xfce4_terminal_title() {
   local title="$*"
   #xfce4-terminal window title
   echo -ne "\\033];${title}\\a" >&2
   #FIXME: tmux isn't detected if tmux was running in user and then you used sudo! so, lame workaround, assume tmux is running if running under 'sudo', if it's not running, then you get extra output, workaround: on stderr!
   if test -n "$TMUX" -o -n "$SUDO_USER"; then
     #echo "!!!!!!!!!!!!!!!!!!!!!!!!!BOO!!!!!!!!!!!!"
     #tmux window title(seen as a tab at the left status bar only)
     echo -ne '\033k'"${title}"'\033\\' >&2
     #tmux pane title (used as window title, in place of xfce4-terminal window title)
     printf '\033]2;'"${title}"'\033\\' >&2
   fi
}

# always pass "$@"
rerunasroot() { # XXX you have to pass "$@"  (also note: looks like $0 is still script name even though this is inside a function!)
  #doneTODO: ensure this script is run as root, OR it becomes root somehow (exec?)
  local iduser
  iduser="$(id -u)"
  #added EUID in case 'id -u' returns the same (wrong)thing(which never happened yet) irregardless of effective user id, and thus will avoid infinite exec loop.
  if test -n "$iduser" -a -n "$EUID"; then
    if test "$iduser" -ne "0" -a "$EUID" -ne "0"; then
      #XXX: re-execute myself as root (needed for ensure below to work ok, for filefrag to be found!)
      #done: fail before exec, if sudo not found!
      #--- warmup sudo
      echo "Not already root, re-executing myself as root by using sudo(required!)..." >&2
      logger "Not already root, re-executing '$0' as root by using sudo."
      #
      #XXX: disabled validate-first because some commands may already not require sudo password(ie. `sync`), but validating first will always ask for one!
      #we use validate to ask for pwd AND to see if we have sudo! or if pwd failed
      #set_xfce4_terminal_title "$(basename "$0") AWAITING FOR YOUR INPUT"
      #sudo --validate --
      #local ec="$?"
      #set_xfce4_terminal_title "$(basename "$0")"
      #if test "$ec" -ne 0 ; then
      #  echo "sudo failed or not found, aborting" >&2
      #  exit 12
      #fi
      #---
      #set -xv #debug
      #XXX if 'sudo' is broken here, ie. it executes `sudo -u user` instead, then we can't detect it, and it will infinite loop! I could probably 'touch' a tmp file and remove it when root, but it's unreliable!
      #preserve DEBUG env.var. setting! 10 June 2021
      exec sudo --preserve-env="DEBUG" -- "$0" "$@"
      #^ the above will exit with 127 if sudo is not found! unless shopt execfail is set (they say) but tested to always exit as such, regardless (btw, shopt -s execfail   sets it to on!)
      echo "Impossibiru" >&2
      exit 3
    fi
  else
    echo "epic fail, bailing out!" >&2
    exit 2
  fi
}

#appendpath code from: /etc/profile which is from ArchLinux package 'filesystem' 
appendpath () {
  for eachpath in "$@"; do
    case ":$PATH:" in
      *:"$eachpath":*)
        #already exists
        ;;
      *)
        PATH="${PATH:+$PATH:}${eachpath}"
        # ${parameter:+word}
        #  Use Alternate Value.  If parameter is null or unset, nothing is substituted, otherwise the expansion  of  word is substituted.
    esac
  done
}

prependpath () {
  for eachpath in "$@"; do
    case ":$PATH:" in
      *:"$eachpath":*)
        #already exists
        ;;
      *)
        PATH="${eachpath}${PATH:+:$PATH}"
        # ${parameter:+word}
        #  Use Alternate Value.  If parameter is null or unset, nothing is substituted, otherwise the expansion  of  word is substituted.
    esac
  done
}


function reloadGTK(){
#src: https://crunchbang.org/forums/viewtopic.php?pid=428525#p428525
#used here: https://github.com/LibVNC/x11vnc/issues/102#issuecomment-528337166

#required: sudo pacman -S pygtk

  python2 - <<END
import gtk

events=gtk.gdk.Event(gtk.gdk.CLIENT_EVENT)
data=gtk.gdk.atom_intern("_GTK_READ_RCFILES", False)
events.data_format=8
events.send_event=True
events.message_type=data
events.send_clientmessage_toall()

END
}

function is_archlinux() {
  local osreleasefile="/usr/lib/os-release"
  if test -f "$osreleasefile"; then
    if grep -qEi "arch ?linux" -- /usr/lib/os-release; then
      #yes
      #use like this: if is_archlinux; then echo yes; fi
      return 0
    #else #no
    fi
  fi
  #no
  return 1
}

function is_gentoo() {
  local osreleasefile="/etc/gentoo-release"
  if test -f "$osreleasefile"; then
    #yup, it's gentoo
    return 0
  fi
  #not gentoo
  return 1
}


function is_loginshell() {
  #ie. you're on console and TERM=linux  or xfce4-terminal is started in login shell mode(actually I don't remember if or how this is possible)
  if shopt -q -p login_shell; then
    #is_login_shell=1
    #ie. if is_loginshell; then echo yes; fi
    return 0
  else
    #is_login_shell=0
    #ie. if ! is_loginshell; then echo not; fi
    return 1
  fi
}


function lockedcall() {
  #XXX highest so far used lockgroup in real scripts is 303
  #^ update that so that we never use same number for too different scripts that should be allowed to run together.

  lockgroup="$1" # aka fd(file descriptor) a value from 300 to 400 let's say.
  #all those with same lock group will use same lock. Works within same script or two different scripts, all attempting to run in parallel will be serialized by using same lockgroup(aka fd)
  shift 1
  if test "$lockgroup" -gt "400" -o "$lockgroup" -lt "300"; then
    echo "'lockgroup' arg(the 1st!) in bash func '$FUNCNAME' must be in range [300-400] but was $lockgroup" >&2
    exit 1
  fi

  func="$1" #bash function name or external command
  shift 1

  lockfile="/tmp/swcode_lockedcall_func_lockgroup_${lockgroup}"
  #file_descriptor_number="204" #can't use this due to shellcheck parsing stopping at the redirection (not just because of that! bash error too)
  (
  set -e
  #locking from, src: http://www.kfirlavi.com/blog/2012/11/06/elegant-locking-of-bash-program/
  #205 is the file descriptor for the lock file - can't use a var, apparently(yeah no kiddin)!
  #flock --wait 60 --exclusive "$lockgroup" >/dev/null 2>&1
  if test -n "$DEBUG" -a "0$DEBUG" != "00"; then
    flock --wait 60 --exclusive 205
    #flock --wait 60 --exclusive "$lockfile"
  else
    flock --wait 60 --exclusive 205         >/dev/null 2>&1
    #flock --wait 60 --exclusive "$lockfile"  >/dev/null 2>&1
  fi
  set +e
  if test -n "$DEBUG" -a "0$DEBUG" != "00"; then
    set -vx
  fi
  "$func" "$@"
  if test -n "$DEBUG" -a "0$DEBUG" != "00"; then
    set +vx
  fi
  ) 205>"${lockfile}" ; rm -- "${lockfile}" 2>/dev/null
  #so even tho it's the same fd (file descriptor) number 205, the fact that we're using different lock filename allows multiple groups to lock and still work. Or, it's just a coincidence that it works! because how can you use same fd for two different files???!
  #the 'rm' doesn't matter, whether or not it's there! it's just nice for cleanup!


  #another way:
  #set -e
  #flock --wait 60 --exclusive "${lockfile}"
  #set +e
}

