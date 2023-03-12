#!/usr/bin/python3 -b
# SPDX-License-Identifier: (GPL-3.0-only OR GPL-2.0-only OR LGPL-2.0-only OR LGPL-2.1-only OR LGPL-3.0-only OR AGPL-3.0-only OR MIT OR MIT-0 OR BSD-2-Clause OR BSD-3-Clause OR CC0-1.0 OR Unlicense OR 0BSD OR Apache-2.0)

#grubmeow = grub MenuEntry Order Window :)
#//grubmero = grub menuentry reorder / reorganize
#TODO: add program name and version! and license
#TODO: save(in some config? or in ~/.cache/ ? but that dir is in /tmp for me) and allow re-applying the order difference, ie. just in case grub-mkconfig was executed since last run. Add an arg for this too.
#-f file or --cfg file //done: add an arg to allow reading a grub.cfg specified on cmdline

#using python-pyqt5 5.14.2-1 in ArchLinux

#doesn't work with pypy: ModuleNotFoundError: No module named 'PyQt5'
#!/usr/bin/pypy3

#things with "src:" are places where I took some code from or got inspiration from

#src: https://stackoverflow.com/questions/42682544/pyqt5-listwidget-add-list-items

#FIXME: ugly workaround for: "Skipping analyzing 'PyQt5': found module but no type hints or library stubs" aka "Skipping analyzing X: found module but no type hints or library stubs", the following commented line is the workaround, as per src: https://mypy.readthedocs.io/en/stable/running_mypy.html  I can recompile python-pyqt5 but no idea how to make this go away currently.
# type: ignore
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QKeyEvent, QKeySequence, QFont
from PyQt5.QtCore import Qt, QTimer
from typing import Any

import sys
#from enum import Enum
from enum import IntFlag, unique, auto
#from enum import Flag, auto, unique
import signal

import argparse

from os import access, R_OK, W_OK
from os.path import isfile
import os
import re
#import time

from types import FrameType# as FrameType

oldsyspath=sys.path
sys.path.append("/swcode/")
import swcode
sys.path=oldsyspath

global app
global win
global args

@unique
class CSI(IntFlag):
    ORIGFILE_INEXISTENT = auto()
    ORIGFILE_UNREADABLE = auto()
    ORIGFILE_NONWRITABLE = auto()

GRUB_CFG_TEXT:Qt.ItemDataRole = Qt.UserRole+1  #technically doesn't have to be +1
NEW_MENUENTRY_NUMBER:Qt.ItemDataRole = Qt.UserRole+2
ORIGINAL_MENUENTRY_NUMBER:Qt.ItemDataRole = Qt.UserRole+3
MENUENTRY_TITLE:Qt.ItemDataRole = Qt.UserRole+4
IS_ME:Qt.ItemDataRole = Qt.UserRole+5

#default grub.cfg filename+location
GRUB_CFG_FILENAME: str = "/boot/grub/grub.cfg"
PROGRAM_NAME:str = "grubmeow"
PROGRAM_WINDOWTITLE:str = "grubmeow - grub menuentry order window"
PROGRAM_VERSION: str = "0.0.3"


#from cutectrl:
#def eprint(*args: Any, **kwargs: Any) -> None:
#    print(*args, file=sys.stderr, **kwargs)

#well ok I don't need my own subclassed QListWidgetItem, I can just use setData and roles, but keeping it for now.
class MyItem(QListWidgetItem):
    def __init__(self):
        super(MyItem, self).__init__(type=QListWidgetItem.UserType)
    def getData(self, role: Qt.ItemDataRole) -> Any:
        return super(MyItem, self).data(role)

class MyQListWidget(QListWidget):

    #should only be called on ME entries!
    def recompute_item(self, item: MyItem) -> None:
        if __debug__:
            is_me=item.getData(IS_ME)
        assert None != is_me, f"Code is bugged: '{is_me}' should be only True or False"
        assert is_me == True, f"{is_me} Function called for non-ME, bug in code!"
        item.setText(f"{item.getData(NEW_MENUENTRY_NUMBER)}: {item.getData(MENUENTRY_TITLE)}")
        font=item.font()
        omen=item.getData(ORIGINAL_MENUENTRY_NUMBER)
        assert type(omen) == int, f"{type(omen)} {omen}"
        nmen=item.getData(NEW_MENUENTRY_NUMBER)
        assert type(nmen) == int, f"{type(nmen)} {nmen}"
        moved_from_orignal_location= (omen != nmen)
        font.setBold(moved_from_orignal_location)
        if moved_from_orignal_location:
            item.setForeground(Qt.green)
        else:
            item.setForeground(Qt.black)
        item.setFont(font)

    def recompute_items(self) -> None:
        me_idx=0
        for idx in range(self.count()):
            item=self.item(idx)
            #if not item.isHidden():
            is_me=item.data(IS_ME)
            assert None != is_me, f"Code is bugged: '{is_me}' should be only True or False"
            if True == is_me: #aka it's a ME, as opposed to a non-ME
                me_idx+=1
                #print(idx, item.isHidden())
                #print(item.data(GRUB_CFG_TEXT))
                item.setData(NEW_MENUENTRY_NUMBER, me_idx)
                self.recompute_item(item)

    def save_items(self) -> bool:
        #FIXME: ensure permissions are retained? see this https://stackoverflow.com/a/5624691
        #hmm, the permissions are already retained probably because/due the file already exists when writing to it!! -rw------- 1 root root 44133 16.05.2020 07:39 /boot/grub/grub.cfg
        #if file doesn't exist they are: -rw-r--r-- 1 root root 44133 17.05.2020 10:43 grub.cfg

        #TODO: backup the previous version(s) !
        #TODO: see if can raise privileges(to root) of running process(which would be non-root), just for this writing! then drop privileges like https://stackoverflow.com/a/22933771 https://stackoverflow.com/questions/2699907/dropping-root-permissions-in-python#2699996
        #TODO hmm maybe using CAP_SETUID while dropped privileges via https://stackoverflow.com/a/44689594 can allow us to raise them again as root?
        #TODO or maybe use a subprocess which always runs as root can and only do the writing, and you can tell it the contents from the now non-root main process?
        #TODO: parse args from here https://stackoverflow.com/a/6921340
        #with open(GRUB_CFG_FILENAME,"w") as f:
        global args
        ret=True
        try:
            print(f"Attempting to save '{args.cfg}' ...")
            with open(args.cfg,"w") as f:
                for idx in range(self.count()):
                    item=self.item(idx)
                    data=item.getData(GRUB_CFG_TEXT)
                    f.write(data)
        except Exception as e:
            #PermissionError
            ret=False

        return ret

    def non_ME(self, last_captured_nonme: str) -> str:
        #last_captured_nonme cannot be changed within the function and thus reflected outside, on the caller, hence why it's returned instead!
        if "" != last_captured_nonme:
            #need to write out the so far collected non-ME block:
            item=MyItem()
            item.setData(IS_ME, False)
            item.setData(GRUB_CFG_TEXT, last_captured_nonme)
            size=len(last_captured_nonme)
            item.setText(f"/// {size} bytes coalesced non-MENUENTRY grub code from grub.cfg")
            item.setData(Qt.ToolTipRole, last_captured_nonme)
            item.setForeground(Qt.gray)
            self.addItem(item)
            #item.setHidden(True)
            #assert item.isHidden()
            return ""
        else:
            return last_captured_nonme
    def __init__(self, parent: QWidget=None):
        global args

        #super(MyQListWidget, self).__init__() #parent)
        #self._listWidget = QListWidget()
        super(MyQListWidget, self).__init__(parent)

        #Rather then assume they aren't pressed on app startup, get their state
        #this is a temporary var:
        current_modifiers = QtWidgets.QApplication.queryKeyboardModifiers() #ie. what's held down at the time of this call!
        #^ these work regardless of virtualkeys settings! ie. shift+alt will not be seen as Meta, so it correctly detects that they are held down!!
        self._alt_helddown:bool = bool(current_modifiers & Qt.AltModifier) #the bool cast is needed, odly enough!
        self._ctrl_helddown:bool = bool(current_modifiers & Qt.ControlModifier)
        self._shift_helddown:bool = bool(current_modifiers & Qt.ShiftModifier)
        #the following are used to build the above:
        self._lalt_helddown:bool = False
        self._lctrl_helddown:bool = False
        self._lshift_helddown:bool = False
        self._ralt_helddown:bool = False
        self._rctrl_helddown:bool = False
        self._rshift_helddown:bool = False

        self._modified=False
        self._state: CSI=0

        #self._listWidget = super(MyQListWidget, self).__init__()
        #src: https://doc.qt.io/qt-5/model-view-programming.html#using-drag-and-drop-with-item-views
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        #listWidget.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)

        #src: https://stackoverflow.com/questions/52873025/pyqt5-qlistview-drag-and-drop-creates-new-hidden-items/52877656#52877656
        self.setDragDropMode(QtWidgets.QListView.InternalMove)
        #self.setDragDropMode(QtWidgets.QListView.DragOnly)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

        #listWidget.selectionModel().selectionChanged.connect(something)
        #QtCore.pyqtSignal().connect(on_key)
        self.keyPressEvent = self.on_key_press
        self.keyReleaseEvent = self.on_key_release
        self.closeEvent = self.on_close_attempt
        #self.quitEvent = self.on_close_attempt #no effect

        self.setGeometry(QtCore.QRect(410, 210, 511, 491))

        #src: https://doc.qt.io/qt-5/qabstractitemview.html#alternatingRowColors-prop
        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)
        self.setAutoScroll(True)
        self.setDragDropOverwriteMode(False)
        self.setTabKeyNavigation(True) #Tab and shift+tab acts like DownArrow key and UpArrow key
        self.setTextElideMode(Qt.ElideNone) #this doesn't matter for this program

        #TODO: add the grub.cfg lines into an external list and only refer to its indexes in the self list
        #done: or make blocks of non MEs, ie. coalesced or collapsed into one item
        #done: add non MEs as items and setHidden(True), see if alt+up moves it, fix it if so
        first_me_item=None
        #with open(GRUB_CFG_FILENAME, "r") as f:
        with open(args.cfg, "r") as f:
            inme=False
            me_level=0
            last_captured_me=""
            mes: List[str]=[]
            count=0
            last_captured_nonme=""
            for line in f:
                sline=line.strip()
                if sline.startswith("menuentry "):
                    assert sline.endswith("{"), sline
                    inme=True
                    me_level+=1
                    assert me_level <=1, f"{me_level} {line}" #for now not expecting a bigger than 1 level, so if found more coding may be needed!
                    #self.non_ME(last_captured_nonme) #changes value of last_captured_nonme! nvm, doesn't work for str, int etc, see: https://www.tutorialspoint.com/how-are-arguments-passed-by-value-or-by-reference-in-python
                    last_captured_nonme=self.non_ME(last_captured_nonme)
                    #if "" != last_captured_nonme:
                    #    #need to write out the so far collected non-ME block:
                    #    item=MyItem()
                    #    item.setData(GRUB_CFG_TEXT, last_captured_nonme)
                    #    size=len(last_captured_nonme)
                    #    item.setText(f"{size} bytes coalesced non-MENUENTRY grub code from grub.cfg")
                    #    item.setData(Qt.ToolTipRole, last_captured_nonme)
                    #    self.addItem(item)
                    #    #item.setHidden(True)
                    #    #assert item.isHidden() #done: this fails! unless it's after self.addItem()!
                    #    #XXX: ok, new strategy, don't hide these because we lose contextual position of the MEs after move
                    #    last_captured_nonme=""
                elif not inme:
                    last_captured_nonme+=line

                # pause, not connected to the above 'if's
                if inme:
                    last_captured_me+=line
                    if sline=="}":
                        me_level-=1
                        assert me_level >= 0, f"{me_level} {line}"
                        assert me_level == 0, f"{me_level} {line}" #for now not expecting a bigger than 1 level, so if found more coding may be needed!
                        if me_level == 0:
                            inme=False
                            mes.append(last_captured_me)
                            count+=1
                            item=MyItem()
                            #first_line_of_lcme=last_captured_me.partition('\n')[0]
                            #just_the_me_title=
                            try:
                                #found = re.search('^menuentry [\'"]{1}([^\'"]+)[\'"]{1}.+{$', first_line_of_lcme)
                                found = re.search('^menuentry [\'"]{1}([^\'"]+)[\'"]{1}.+{$', last_captured_me, re.MULTILINE)
                                just_the_me_title = found.group(1)  #this will throw, if unexpected shie
                                #print(found.group(0), found.group(1))
                            except:
                                #print(first_line_of_lcme)
                                eprint(last_captured_me)
                                raise
                            item.setData(GRUB_CFG_TEXT, last_captured_me)
                            item.setData(NEW_MENUENTRY_NUMBER, count)
                            item.setData(ORIGINAL_MENUENTRY_NUMBER, count)
                            item.setData(IS_ME, True)
                            item.setData(MENUENTRY_TITLE, f"{just_the_me_title}")
                            self.recompute_item(item)
                            item.setData(Qt.ToolTipRole, last_captured_me)
                            #item.setData(Qt.StatusTipRole, f"originally in the position number {count}") #cannot be shown unless win.show() is used
                            self.addItem(item)
                            if None == first_me_item:
                                first_me_item = item
                            last_captured_me=""

                assert me_level >= 0
            #done: this code block is duplicated! dedupe it!
            #outside of 'for', for the last non-ME block/line(s):
            self.non_ME(last_captured_nonme)

        #i=0
        #for each_me in mes:
        #    i+=1
        #    print(i, each_me)

        ##ls = ['test4', 'test2', 'test3', "hjskhfkgweiyfgowefhoewhfwoefowe"]
        #item = MyItem()
        ##font = QtGui.QFont()
        ##font.setBold(True)
        ##font.setWeight(75) #TODO what is this?
        #item.setText("blah0")
        ##item.setData(Qt.UserRole+1,"meh")
        ##item.setData(Qt.UserRole+2,"beh")
        #item.setData(GRUB_CFG_TEXT,"beh")
        #self.addItem(item)
        ##listWidget.addItem('test2')
        ##listWidget.addItem('test3')

        #self.addItems(ls)

        #font = QtGui.QFont("Arial", 13, QFont.Regular)
        font = QtGui.QFont("Arial", 13)
        self.setFont(font)
        #self.setCurrentRow(0)
        self.setCurrentItem(first_me_item)
        self.scrollToItem(self.currentItem(), QtWidgets.QAbstractItemView.PositionAtTop)
        #TODO: save/restore last row position, as current.

        #self.show()

    #def something(self):
    #    print(self)

    def recompute_state(self) -> None:
        self._modified=not self._modified
        #FIXME:
        orig:str =""
        curr:str =""
        #TODO: handle the case when file went away, for wtw reason!
        ret:CSI = 0
        #TODO: copy args.cfg into a global grubcfg var and use it instead! depending on args.cfg directly is bad
        if not isfile(args.cfg):
            ret|=CSI.ORIGFILE_INEXISTENT
        else:
            #extra
            if not access(args.cfg, W_OK):
                ret|=CSI.ORIGFILE_NONWRITABLE
                #done: tell in dialog that the file is gone
            try:
                with open(args.cfg,"r") as f:
                    orig+=f.read()
            except Exception as e:
                eprint(f"While attempting to read {args.cfg}, got {e}")
                assert type(e) != FileNotFoundError, type(e)
                #te=type(e)
                #if te == FileNotFoundError:
                #    ret|=CSI.ORIGFILE_INEXISTENT
                #PermissionError or some read error
                ret|=CSI.ORIGFILE_UNREADABLE
                pass
        #don't bother comparing if original file doesn't exist, assume modified then!
        if 0 == ret:
            for idx in range(self.count()):
                item=self.item(idx)
                data=item.getData(GRUB_CFG_TEXT)
                curr+=data
            self._modified = (curr != orig)
        else:
            self._modified = True

        #set:
        self._state=ret

    def on_close_attempt(self,event) -> None:
        #print("close event") #, event)
        self.recompute_state()

        cd = QMessageBox(self)

        if self._modified:
            msg="Save before quit?"
            icon=QMessageBox.Warning
        else:
            msg="Exit program?"
            icon=QMessageBox.Information

        #print(self._state)
        if bool(self._state & CSI.ORIGFILE_NONWRITABLE):
            msg="Attempt to "+msg+f"\nWarning: original file is no longer writable(it was at startup though). File is {args.cfg}"
            icon=QMessageBox.Critical
        elif bool(self._state & CSI.ORIGFILE_INEXISTENT):
            msg+=f"\nOriginal file seems gone. File is {args.cfg}"
        elif bool(self._state & CSI.ORIGFILE_UNREADABLE):
            msg+=f"\nCouldn't determine if changes were made because original file is unreadable currently! File is {args.cfg}"

        cd.setIcon(icon)

        cd.setText(msg)
        #TODO: detect when modified and only then Present the Save button? or even the entire dialog
        #cd.setStandardButtons(
        #    QMessageBox.Save | QMessageBox.Close | QMessageBox.Cancel,
        #    )
        #    #QMessageBox.Save)
        close_button = QPushButton("Close/&Quit")
        cancel_button = QPushButton("C&ancel/ESC") #Cancel
        cd.addButton(close_button, QtWidgets.QMessageBox.RejectRole)
        cd.addButton(cancel_button, QtWidgets.QMessageBox.RejectRole)
        cd.setEscapeButton(cancel_button) #ESC is Cancel

        save_button = QPushButton("&Save") #needed for 'if' below
        if self._modified:
            save_button.setDefault(True)
            cd.setDefaultButton(save_button) #redundant?!!
            cd.addButton(save_button, QtWidgets.QMessageBox.AcceptRole)
        else:
            close_button.setDefault(True)
            cd.setDefaultButton(close_button)
        #reply = cd.exec() #int value when custom buttons are used
        cd.exec()
        #reply=cd.result()
        reply=cd.clickedButton()

        #if reply == QMessageBox.Close:
        if reply == close_button:
            #print("close accepted")
            event.accept()
        #elif reply == QMessageBox.Cancel:
        elif reply == cancel_button:
            #print("cancelled, don't quit")
            event.ignore()
        #elif reply == QMessageBox.Save:
        elif reply == save_button:
            #print("save&quit")
            #app.quit()
            #done: accept only if save was successful
            if self.save_items():
                event.accept()
            else:
                #TODO: make this an info box? and then re-show the save/close/cancel box afterwards?
                eprint("Save failed! Retry?")
                event.ignore()
        else:
            raise Exception(f"impossible {reply}")

    def recompute_modifiers(self) -> None:
        self._alt_helddown = self._lalt_helddown | self._ralt_helddown
        self._ctrl_helddown = self._lctrl_helddown | self._rctrl_helddown
        self._shift_helddown = self._lshift_helddown | self._rshift_helddown

    #def dragMoveEvent(self, event):
    #    print("dragMoveEvent")
    #    event.accept()

    #def dragEnterEvent(self, event):
    #    print("dragEnterEvent")
    #    event.accept()

    #step can be positive or negative, usually +-1
    def find_row(self, fro:int,step:int=1) -> int:
        which_row=fro
        length=self.count()
        while True:
        #for which_row in range(fro+step,step, step):
            if which_row < 0 or which_row >= length:
                #print(f"hit range 0 <= {which_row} < {length}")
                break
            item_at_row=self.item(which_row)
            is_me=item_at_row.data(IS_ME)
            assert None != is_me, f"Code is bugged: '{is_me}' should be only True or False"
            if None == item_at_row:
                #print("hit none at index {which_row}")
                break
            #elif not item_at_row.isHidden(): #self.isItemHidden(item_at_row):
            elif True == is_me: #aka it's a ME, as opposed to a non-ME
                return which_row
            which_row+=step
        return -1


    def dropEvent(self, event):
        #print("dropEvent", self.count())
        #event.accept() #calling this and then super() will delete an item on each call!
        super(MyQListWidget, self).dropEvent(event)
        self.on_move()

    def on_move(self):
        #print("on_move pre", self.count())
        self.recompute_items()
        #print("on_move aft", self.count())

    def on_key_release(self, event: QKeyEvent):
        assert event.type() == event.KeyRelease, event.type()
        modifiers = event.modifiers()
        if event.nativeScanCode() == 64: #LAlt
            self._lalt_helddown = False
        elif event.nativeScanCode() == 37: #LCtrl
            self._lctrl_helddown = False
        elif event.nativeScanCode() == 50: #LShift
            self._lshift_helddown = False
        elif event.nativeScanCode() == 62: #RShift
            self._rshift_helddown = False
        elif event.nativeScanCode() == 105: #RCtrl
            self._rctrl_helddown = False
        elif event.nativeScanCode() == 108: #RAlt
            self._ralt_helddown = False
        self.recompute_modifiers()
        super(MyQListWidget,self).keyReleaseEvent(event)
        #print("shift=",self._shift_helddown, "ctrl=",self._ctrl_helddown, "alt=",self._alt_helddown)

    def on_key_press(self, event: QKeyEvent):
        assert event.type() == event.KeyPress, event.type()
        #global_modifiers = QtWidgets.QApplication.keyboardModifiers()
        #current_modifiers = QtWidgets.QApplication.queryKeyboardModifiers()
        #global app
        #modifiers = app.keyboardModifiers() #still broken in the same way as QtWidgets.QApplication.keyboardModifiers()
        modifiers = event.modifiers()
        #assert QtWidgets.QApplication.keyboardModifiers == event.modifiers #not true
        #assert QtWidgets.QApplication.keyboardModifiers() == event.modifiers() #not true always
        #alt_held = (modifiers == Qt.AltModifier)  #odd! The "&" operation won't work! ah because non zero(actually some object eg. <PyQt5.QtCore.Qt.KeyboardModifiers object at 0x7fd1f561fdd0>) doesn't equal True!!
        #alt_held = (modifiers & Qt.AltModifier) == Qt.AltModifier
        #alt_held:bool = (modifiers & Qt.AltModifier)
        #if event.key() == Qt.Key_Alt:
        #    self._alt_helddown = True
        #elif event.key() == Qt.Key_AltGr:  #on my keyboard it's RAlt, but it's not detected here via key()!
        #    print("-------AltGr")
        #elif event.key() == Qt.Key_Control:
        #    self._ctrl_helddown = True
        #elif event.key() == Qt.Key_Shift:
        #    self._shift_helddown = True
        #elif event.key() == 16777250:
        #    self._shift_helddown = True
        #    self._alt_helddown = True
        #    #yes really, it's called Meta aka pressing and holding Shift then Alt key.
        #    #see: https://keycode.info/  to see that ^
        if event.nativeScanCode() == 64: #Alt
            self._lalt_helddown = True
        elif event.nativeScanCode() == 37: #Ctrl, or Lshift+Rshift+a  yes, odd!
            self._lctrl_helddown = True
        elif event.nativeScanCode() == 50: #Shift
            self._lshift_helddown = True
        elif event.nativeScanCode() == 62: #RShift
            self._rshift_helddown = True
        elif event.nativeScanCode() == 105: #RCtrl
            self._rctrl_helddown = True
        elif event.nativeScanCode() == 108: #RAlt
            self._ralt_helddown = True
        self.recompute_modifiers()

        cur=self.currentItem()
        cur_row=self.currentRow()
        key=event.key()
        #mehFIXME: with event.modifiers(), when holding ctrl+shift+alt , alt isn't detected as held, but it's detected as press event(ie. when it's the third pressed key), wtf?! ok, LAlt and RAlt(true for Shift and Ctrl too) when pressed both, no Alt is detected, and Shift+Alt doesn't detect Shift but the prev. state (of either being held) remains. Things are more odd with QtWidgets.QApplication.keyboardModifiers() where two modifiers have to be pressed for any bool to show True !! Ok the problem is that when press+hold Key_Alt then Key_Shift (or in reverse order) then the latter event.key() == 0, which is VERY odd!  well of course it was because alt+shift was set to "Change layout option" aka keyboard layout in `xfce4-keyboard-settings`! so that fixes alt+shift combination! ok wait, something is still wrong: shift+alt gives 16777250 instead of 16777251 which is alt! it's not a pyqt5 issue though, since it happens inside `xfce4-keyboard-settings` also, in the input field; no other combinations give different event.key() values!
        #print(Qt.ShiftModifier, Qt.ControlModifier, Qt.AltModifier) #numbers!
        #print(modifiers & Qt.ShiftModifier, modifiers & Qt.ControlModifier, modifiers & Qt.AltModifier)
        #print(modifiers == Qt.ShiftModifier, modifiers == Qt.ControlModifier, modifiers == Qt.AltModifier)
        #print(bool(modifiers & Qt.ShiftModifier), bool(modifiers & Qt.ControlModifier), bool(modifiers & Qt.AltModifier))
        #print("shift=",self._shift_helddown, "ctrl=",self._ctrl_helddown, "alt=",self._alt_helddown)
        assert QtCore.Qt.AltModifier == Qt.AltModifier  #identic because I'm importing Qt from QtCode, heh
        #print(cur, cur.text(), modifiers, event)
        was_moved=False
        no_super=False
        if event.key() == QtCore.Qt.Key_Escape or event.matches(QKeySequence.Quit):
            #print("closing by key event", event.key())
            self.close()
            #keep_alive()
            #app.quit() #bypasses the close event!
            #reached when cancelling the close!
            no_super=True
        elif event.matches(QKeySequence.Save):
            #print("save")
            #done: save
            if self.save_items():
                event.accept()
            else:
                eprint("Save failed! Retry?")
                event.ignore()
            no_super=True
        elif event.matches(QKeySequence.Copy):
            #selected= self.selectionModel().selectedIndexes()
            #assert len(selected) <= 1
            #if len(selected) == 1:
            #    firstselected=selected[0]
            #    row = firstselected.row()
            #else:
            #    row=0
            print("copy", cur.text())
            #TODO:
        elif event.matches(QKeySequence.Cut):
            print("cut")
            #TODO:
        elif event.matches(QKeySequence.Paste):
            print("paste")
            #TODO:
        elif self._alt_helddown:
            if key == Qt.Key_Down:
                #print("alt+down")
                #TODO: find the row to move it to, must be in place of an already existing ME aka menuentry; OR, hide the items that aren't supposed to be seen!
                #TODO: do the finding of right row for drag&drop too!
                #move_to_row=cur_row + 1
                move_to_row=self.find_row(cur_row+1, +1)
                if -1 != move_to_row:
                    taken=self.takeItem(cur_row)
                    self.insertItem(move_to_row, taken)
                    was_moved=True
                else:
                    print("no move down")
                    no_super=True
                #TODO: maybe put this was_moved detection in an event?
            elif key == Qt.Key_Up:
                #print("alt+up")
                #move_to_row=cur_row - 1
                move_to_row=self.find_row(cur_row-1, -1)
                if -1 != move_to_row:
                    taken=self.takeItem(cur_row)
                    self.insertItem(move_to_row, taken)
                    #self.setCurrentRow(cur_row) #only needed for up to not end up on second row due to takeItem
                    #self.setCurrentRow(move_to_row)
                    #font=taken.font()
                    #font.setBold(True)
                    #taken.setFont(font)
                    was_moved=True
                else:
                    print("no move up")
                    no_super=True
        elif event.nativeScanCode() in [49,135]: #49=` key(left of key '1', up of key 'Tab')133=LWinKey, 135=RMenuKey(this one repeats when held!)
            #global win
            #win.showToolTip()
            #QtWidgets.QToolTip.hideText()
            #QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "message")
            #done: find out how to make it show current item's tooltip? hmm wait
            #see https://doc.qt.io/qtforpython/PySide2/QtWidgets/QToolTip.html
            if QtWidgets.QToolTip.isVisible():
                QtWidgets.QToolTip.hideText()
            else:
                QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), cur.toolTip())
            #QtWidgets.QToolTip.repaint() #FIXME: make this show or hide immediately instead of waiting like 0.5sec before doing that!
            no_super=True


        #else:
        #    print("super")
        #    super(MyQListWidget,self).keyPressEvent(event)
        #print('key=',event.key(), "nativeScanCode=",event.nativeScanCode(), "nativeModifiers=", event.nativeModifiers(), "nativeVirtualKey=", event.nativeVirtualKey())
        if __debug__:
            beforesuper_key=event.key()
            beforesuper_nsc=event.nativeScanCode()
            beforesuper_nm=event.nativeModifiers()
            beforesuper_nvk=event.nativeVirtualKey()
        #time.sleep(1)
        #print("super")
        if not no_super:
            super(MyQListWidget,self).keyPressEvent(event)
        assert event.key() == beforesuper_key, f"{event.key()}!={beforesuper_key}"
        assert event.nativeScanCode() == beforesuper_nsc, f"{event.nativeScanCode()}!={beforesuper_nsc}"
        assert event.nativeModifiers() == beforesuper_nm, f"{event.nativeModifiers()}!={beforesuper_nm}"
        assert event.nativeVirtualKey() == beforesuper_nvk, f"{event.nativeVirtualKey()}!={beforesuper_nvk}"

        #XXX: probably must be after super():
        if was_moved:
            self.on_move()
            self.setCurrentRow(move_to_row)

        #XXX: must be after super():
        movedtoitem=self.currentItem()
        #print("cursor moved to:", movedtoitem.text())
        #print("data of first user role=", movedtoitem.data(GRUB_CFG_TEXT))
        #print(modifiers & Qt.ShiftModifier, modifiers & Qt.ControlModifier, modifiers & Qt.AltModifier, modifiers & Qt.Key_Alt)
        #print(modifiers == Qt.ShiftModifier, modifiers == Qt.ControlModifier, modifiers == Qt.AltModifier) #obvious crap
        #print(bool(modifiers & Qt.ShiftModifier), bool(modifiers & Qt.ControlModifier), bool(modifiers & Qt.AltModifier), bool(modifiers & Qt.Key_Alt))
        #if self._shift_helddown and self._ctrl_helddown:
        #print('key=',event.key(), "nativeScanCode=",event.nativeScanCode(), "nativeModifiers=", event.nativeModifiers(), "nativeVirtualKey=", event.nativeVirtualKey())
        #XXX WARNING: the following shows it only when the second key is pressed, ie. shows shift is true only when a is pressed in shift+a
        #print(bool(global_modifiers & Qt.ShiftModifier), bool(global_modifiers & Qt.ControlModifier), bool(global_modifiers & Qt.AltModifier))
        #print(bool(current_modifiers & Qt.ShiftModifier), bool(current_modifiers & Qt.ControlModifier), bool(current_modifiers & Qt.AltModifier))

#def keep_alive():
#    global app
#    try:
#        app.lastWindowClosed.disconnect(keep_alive)
#    except TypeError as e:
#        print(e)
#        pass
#    global win
#    #win.setVisibility(QtGui.QWindow.Minimized) #win must be QWindow type here, not QMainWindow
#    #print(win)
#    reply = QMessageBox.question(
#            win, "Message",
#            "Are you sure you want to quit? Any unsaved work will be lost.",
#            QMessageBox.Save | QMessageBox.Close | QMessageBox.Cancel,
#            QMessageBox.Save)
#
#    print(reply)
#    if reply == QMessageBox.Close:
#        print("close in keep_alive")
#        app.quit()
#    elif reply == QMessageBox.Save:
#        print("saving")
#        app.quit()
#    elif reply == QMessageBox.Cancel:
#        print("cancelled")
#        #FIXME: the main window can be already closed here, hence why Ctrl+C in console was needed to can quit...
#        app.lastWindowClosed.connect(keep_alive)
#    else:
#        raise Exception(f"impossible {reply}")

#FIXME: get the tooltip to update even though mouse didn't move but underlaying items order changed, maybe see: https://stackoverflow.com/questions/19427625/continuously-updating-tooltip

def signal_handler(sig: signal.Signals, frame: FrameType) -> None:
    eprint('\nYou pressed Ctrl+C! Exiting...')
    QApplication.quit()
    #sys.exit(0)

##needed to catch Ctrl+C 1of3, src: https://stackoverflow.com/questions/4938723/what-is-the-correct-way-to-make-my-pyqt-application-quit-when-killed-from-the-co/11705366#11705366
## You HAVE TO reimplement QApplication.event, otherwise it does not work.
## I believe that you need some python callable to catch the signal
## or KeyboardInterrupt exception.
#class MeApplication(QApplication):
#    def event(self, e):
#        return QApplication.event(self, e)

def parse_args():
    parser = argparse.ArgumentParser(allow_abbrev=False, add_help=True)
    parser.add_argument('-f', '--cfg', type=str, nargs=1, default=GRUB_CFG_FILENAME, help='specify which grub.cfg file to use', required=False)
    #parser.add_argument('-f', '--cfg', type=str, default=GRUB_CFG_FILENAME, help='specify which grub.cfg file to use', required=False)
    global args
    args = parser.parse_args()
    #no idea why it's a list of 1 string here! maybe because nargs=1 is specified? yup that's true! FIXME: make 'argparse' module with nargs=1 act as if nargs wasn't specified and thus have the arg be of type str and not list[str] !
    #workaround:
    if type(args.cfg) == list:
        assert type(args.cfg) == list, f"{type(args.cfg)} {args.cfg}"
        assert len(args.cfg) == 1, args.cfg
        args.cfg=args.cfg[0]

    assert type(args.cfg) == str, f"{type(args.cfg)} {args.cfg}"


def check_args() -> None:
    #f=args.cfg[0]
    f=args.cfg
    assert type(f) == str, f"{type(f)} {f}"
    if not isfile(f):
        #done: to stderr!
        eprint(f"Cannot find file {f}")
        sys.exit(1)
    if not access(f, R_OK):
        eprint(f"Cannot read file {f}")
        sys.exit(1)
    if not access(f, W_OK):
        eprint(f"Cannot write file {f}")
        sys.exit(1)

def main():
    signal.signal(signal.SIGINT, signal_handler)

    app = QApplication(sys.argv)
    #app = MeApplication(sys.argv) 2of3
    # And start a timer to call Application.event repeatedly.
    # You can change the timer parameter as you like.
    #app.startTimer(500) #needed to catch Ctrl+C 3of3


    #another way to catch/run Ctrl+C 1of1, src: https://stackoverflow.com/questions/4938723/what-is-the-correct-way-to-make-my-pyqt-application-quit-when-killed-from-the-co/4939113#4939113
    timer = QTimer()
    timer.start(500)  # You may change this if you wish.
    timer.timeout.connect(lambda: None)  # Let the interpreter run each 500 ms.

    #app.setQuitOnLastWindowClosed(False)
    app.setQuitOnLastWindowClosed(True) #using another way, with closeEvent now
    #app.lastWindowClosed.connect(keep_alive)
    win = QtWidgets.QMainWindow()
    #win.statusBar().showMessage('Message in statusbar.') #probably only works if win.show() is used!

    #win = QtGui.QWindow()
    #win.show()

    #window = QtGui.QWindow()
    #window.show()
    i=MyQListWidget()
    #i=MyQListWidget(win)
    i.show()
    #win.closeEvent = self.on_close_attempt
    #win.show()  #works but doesn't detect alt+f4

    sys.exit(app.exec_())

#moved to /swcode/swcode.py
##src: https://github.com/barneygale/elevate/blob/master/elevate/posix.py
#def elevate(graphical=False):
#    if os.geteuid() == 0:
#        return
#
#    #done: is shlex.quote() needed for sys.argv values? I guess not because it's an array of args so you know where they each start/end, AND it's not using subshell!
#
#    #not good enough to run the "./a.py" arg!
#    #args = [sys.executable] + sys.argv
#    #but this is:
#    args = [sys.executable]
#    args.append(os.path.realpath(__file__))
#    args+=sys.argv[1:]
#    eprint("Will execute as root:",args)
#    commands = []
#
#    #FIXME: if graphical, need to preserve env. vars $DISPLAY and $XAUTHORITY (at least), else it won't start! and pkexec clears them also!  it works fine with 'sudo' though!
#    if graphical:
#        if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
#            commands.append(["pkexec"] + args)
#            commands.append(["gksudo"] + args)
#            commands.append(["kdesudo"] + args)
#
#    #with 'sudo', under X, will get this output: "QStandardPaths: XDG_RUNTIME_DIR not set, defaulting to '/tmp/runtime-root'"
#    commands.append(["sudo"] + args)
#
#    #this 'args' shadows the prev. 'args' inside the 'for'
#    for args in commands:
#        try:
#            os.execlp(args[0], *args)
#        except OSError as e:
#            # errno.ENOENT aka FileNotFoundError src: https://docs.python.org/3/library/exceptions.html#FileNotFoundError
#            #or, last command attempted, then rethrow exception
#            if e.errno != errno.ENOENT or args[0] == "sudo":
#                raise
#
#def is_string_empty(s:str) -> bool:
#    assert type(s) in [str, type(None)], type(s)
#    return None == s or s.strip()==""
#
#def is_X() -> bool:
#    #print(is_string_empty(""))
#    #is_string_empty(0)
#    disp=os.environ.get("DISPLAY")
#    return not is_string_empty(disp)

if __name__ == '__main__':
    parse_args()
    #done: don't coredump if not in X, eg. check DISPLAY env. var.
    if not swcode.is_X():
        eprint("Avoiding coredump when not running inside X. Ncurses version not yet implemented") #TODO
        sys.exit(1)

    #TODO: only elevate if necessary! or if cmdline arg explicitly says so; or never if it says so!
    swcode.elevate(__file__, graphical=False)
    check_args()
    main()
    #TODO: allow multiple selection and move; XXX: should non-consecutively selected ones coalesce into a group of consecutives after first move??!
    #TODO: make a ncurses variant for when X isn't running

#Keep this last:
#vim filetype is set to python below, otherwise vim will use tabs instead of spaces for indentation when pypy3 is interpreter
# vim: set ft=python
