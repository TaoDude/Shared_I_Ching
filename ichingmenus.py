#!/usr/bin/env python3
# requires `pifacecad` to be installed
#
# Initialisation and Menu Setup Routine based on radio.py from examples and sysinfo.py Service
#

from time import sleep
import os
import sys
import signal
import shlex
import math
import lirc

PY3 = sys.version_info[0] >= 3
if not PY3:
    print("I Ching only works with `python3`.")
    sys.exit(1)

from threading import Barrier  # must be using Python 3
import subprocess
import pifacecommon
import pifacecad
from pifacecad.lcd import LCD_WIDTH

CHECK_INTERVAL = 1          # 1 second debugging delay for checking for menu actions the screen
TOGGLE_INTERVAL = 1         # 1 second toggle delay between symbols and words
STEP_INTERVAL = 0.5         # 0.5 second delay between Character display shifts
PAUSE_INTERVAL = 2          # 2 seconds debugging delay to capture what happened before return from interrupts
CONFIRM_DELAY = 5           # 5 seconds to confirm exit request.
GET_IP_CMD = "hostname --all-ip-addresses"
STOP_SYSINFO_CMD = "service pifacecadsysinfo stop"

#
#   Set up bitmap variables for I Ching symbols
#
i_tl_symbol = pifacecad.LCDBitmap(
    [0x10, 0x1f, 0x11, 0x15, 0x15, 0x15, 0x11, 0x1f])
i_bl_symbol = pifacecad.LCDBitmap(
    [0x11, 0x15, 0x15, 0x15, 0x11, 0x1f, 0x10, 0x10])
i_tr_symbol = pifacecad.LCDBitmap(
    [0x01, 0x1f, 0x11, 0x15, 0x15, 0x15, 0x11, 0x1f])
i_br_symbol = pifacecad.LCDBitmap(
    [0x11, 0x15, 0x15, 0x15, 0x11, 0x1f, 0x01, 0x01])
i_tl_symbol_index, i_tr_symbol_index, i_bl_symbol_index, i_br_symbol_index = 0, 1, 2, 3
ching_tl_symbol = pifacecad.LCDBitmap(
    [0x0, 0x0, 0x0, 0x3, 0x6, 0xc, 0x10, 0x3])
ching_bl_symbol = pifacecad.LCDBitmap(
    [0x6, 0xc, 0x10, 0x3, 0x6, 0xc, 0x10, 0x0])
ching_tr_symbol = pifacecad.LCDBitmap(
    [0x0, 0x10, 0x18, 0x14, 0x12, 0x12, 0x11, 0x11])
ching_br_symbol = pifacecad.LCDBitmap(
    [0x11, 0x13, 0x12, 0x14, 0x14, 0x18, 0x010, 0x0])
ching_tl_symbol_index, ching_tr_symbol_index, ching_bl_symbol_index, ching_br_symbol_index = 4, 5, 6, 7

# 5x8 Custom Bitmap hEXAGRAM construction values

blank_space_bits = 0b00000          # Top and bottom lines of 5x8 display will always be blank
old_yang_bits = 0b10101             # Short-form of '--0--' to fit LCD limitations = 21 Decimal
young_yang_bits = 0b11111           # Short-form of '-----' to fit LCD limitations = 31 Decimal
old_yin_bits = 0b10001              # Short-form of '--X--' to fit LCD limitations = 17 Decimal
young_yin_bits = 0b11011            # Short-form of '-- --' to fit LCD limitations = 27 Decimal

# Custom Bitmap indices - NOTE - re-uses splash screen locations as only 8 custom bitmaps supported by
# PiFaceCAD module.

hexagram_index = 0

def run_cmd(cmd):
    return subprocess.check_output(cmd, shell=True).decode('utf-8')


def splash_loop():                      # Display startup splash screens until a button is pressed.
    global menus
    global display_lcd
    display_lcd.splash = True           # Another splash follows this one, so disable menu generation.
    display_toggle = True               # Start with the words.
    menus.active = False                # Flag still processing startup screens
    menus.waiting = True                # Flag waiting for button press
    while menus.waiting:                # If no button was pressed Update Display Splash Screen
        if display_toggle:
            cad.lcd.clear()
            cad.lcd.write("I Ching Hexagrams")
            cad.lcd.set_cursor(1,1)
            cad.lcd.write("Press a Button")
            display_toggle = False
        else:                           # alternate with I Ching symbols moving across the screen
            cad.lcd.clear()
            cad.lcd.set_cursor(0,0)
            cad.lcd.write_custom_bitmap(i_tl_symbol_index)
            cad.lcd.write_custom_bitmap(i_tr_symbol_index)
            cad.lcd.write_custom_bitmap(ching_tl_symbol_index)
            cad.lcd.write_custom_bitmap(ching_tr_symbol_index)
            cad.lcd.set_cursor(0,1)
            cad.lcd.write_custom_bitmap(i_bl_symbol_index)
            cad.lcd.write_custom_bitmap(i_br_symbol_index)
            cad.lcd.write_custom_bitmap(ching_bl_symbol_index)
            cad.lcd.write_custom_bitmap(ching_br_symbol_index)
            sleep(STEP_INTERVAL)        # Animation delay
            for i in range(12):         # Proceed with animation if no buttom was pressed
                if menus.waiting == False: break
                cad.lcd.move_right()
                sleep(STEP_INTERVAL)    # Animation delay
            for i in range(12):         # Proceed with animation if no buttom was pressed
                if menus.waiting == False: break
                cad.lcd.move_left()
                sleep(STEP_INTERVAL)    # Animation delay
            display_toggle = True
        sleep(TOGGLE_INTERVAL)          # Wait for a button press before repeating.


def help_splash():                      # Display Help splash screen.
    global menus
    global display_lcd
    menus.waiting = True                # Flag waiting for button press
    menus.active = False                # Flag still processing startup screens
    display_lcd.splash = False          # No splash follows this, so allow menu generation.
#
#   Set up display of Help screen
#
    display_lcd.topline = "Key:  IR  <^>"
    display_lcd.botline = "1 2 3 4  Back"
#
#   Display Help Screen
#
    cad.lcd.clear()
    cad.lcd.set_cursor(1,0)
    cad.lcd.write(display_lcd.topline)
    cad.lcd.set_cursor(1,1)
    cad.lcd.write(display_lcd.botline)
    while menus.waiting:                # Wait until a button is pressed
        sleep(PAUSE_INTERVAL)


def main_loop():
    global menus
    global display_lcd
    global hexagrams
    menus.active = True                                 # Flag program is running normally
    while menus.active:
        if menus.paused:
#
#   If paused is True, we are partway through a menu change, so process Menu Selection
#
            sleep(PAUSE_INTERVAL)                       # Debugging wait before updating the display
            if menus.menu_level == 1:                   # Process Level 1 Menu
                menus.menu_level = 2                    # Will be at Level 2 when finished.
                if menus.selected_action == -1:         # Switch '-1' = 'No action Required'.
                    cad.lcd.clear()                     # Send debug message to show that we got here
                    cad.lcd.set_cursor(0,0)
                    cad.lcd.write("Debugging Trap")
                    cad.lcd.set_cursor(0,1)
                    cad.lcd.write("Please Wait...")
                    sleep(CHECK_INTERVAL)               # Wait for it to be seen
                    menus.begin_menu()                  # Redisplay MAIN_MENU Option 0
                elif menus.selected_action == 0:        # Switch 0  = 'Cast' selected
                    menus.current_menu_index = 0
                    menus.active_menu = CAST_MENU
                    menus.update_display()
                    menus.selected_action = -1          # prevent further background processing
                elif menus.selected_action == 1:        # Switch 1 = 'Game' selected
                    menus.current_menu_index = 0
                    menus.active_menu = GAME_MENU
                    menus.update_display()
                    menus.selected_action = -1          # prevent further background processing
                elif menus.selected_action == 2:        # Switch 2 = 'Settings' selected
                    menus.current_menu_index = 0
                    menus.active_menu = OPTION_MENU
                    menus.update_display()
                    menus.selected_action = -1          # prevent further background processing
                elif menus.selected_action == 3:        # Switch 3 = 'Quit' selected
                    cad.lcd.clear()
                    cad.lcd.set_cursor(0,0)
                    cad.lcd.write("Quit? Select = Y")   # Ask for confirmation
                    cad.lcd.set_cursor(8,1)
                    cad.lcd.write("Back = N")
                    menus.exit_pending = True           # tell switch handlers Quit is pending
                    sleep(CONFIRM_DELAY)                # wait for the user to confirm or back out
                    if menus.exit_pending:              # If user does not confirm, time out and continue
                        menus.exit_pending = False
                        cad.lcd.clear()
                        cad.lcd.set_cursor(3,0)
                        cad.lcd.write("Timed Out.")
                        cad.lcd.set_cursor(2,1)
                        cad.lcd.write("Quit Aborted.")
                        sleep(PAUSE_INTERVAL)
                        menus.begin_menu()              # Restart with MAIN_MENU Option 0
                        menus.selected_action = -1      # prevent further background processing
                    else:                               # User has decided.
                        if menus.no_quit:               # Quit aborted, back to waiting
                            menus.begin_menu()          # set up MAIN_MENU Option 0
                        else:
                            menus.active = False        # Disable Interrupt processing
                            break                       # Exit loop.
                else:                                   # Trap exceptions
                    cad.lcd.clear()
                    cad.lcd.set_cursor(1,0)
                    cad.lcd.write("Unknown Option")
                    cad.lcd.set_cursor(1,1)
                    cad.lcd.write("Press Back...")
#
# Level 2 menus have no code to access yet, so display hidden parameters for now.
#
            else:                                       # Display hidden paramters of selected menu option
                cad.lcd.clear()
                cad.lcd.set_cursor(0,0)
                local_page = menus.current_item['page']
                local_option = menus.current_item['position']
                local_message = "Page " + str(local_page) + " Option " + str(local_option)
                cad.lcd.write(local_message)
                cad.lcd.set_cursor(1,1)
                cad.lcd.write("Press Back...")
            menus.paused = False                        # Clear interrupt in progress flag.


# Menu Structures

MAIN_MENU = [
    {'name': "Cast",
     'page': 0,
     'position': 0,
     'action': "Cast Hexagram",
     'new_menu': 1},
    {'name': "Game",
     'page': 0,
     'position': 1,
     'action': "Play Game",
     'new_menu': 2},
    {'name': "Settings",
     'page': 0,
     'position': 2,
     'action': "Change Settings",
     'new_menu': 3},
    {'name': "Quit",
     'page': 0,
     'position': 3,
     'action': "Quit Program",
     'new_menu': -1},
]

CAST_MENU = [
    {'name': "Stalks",
     'page': 1,
     'position': 0,
     'action': "Use Stalks",
     'new_menu': 0},
    {'name': "Coins",
     'page': 1,
     'position': 1,
     'action': "Use Coins",
     'new_menu': 0},
    {'name': "Dice",
     'page': 1,
     'position': 2,
     'action': "Use Dice",
     'new_menu': 0},
    {'name': "User",
     'page': 1,
     'position': 3,
     'action': "User Data",
     'new_menu': 0},
]

GAME_MENU = [
    {'name': "Lines",
     'page': 2,
     'position': 0,
     'action': "Solve Lines",
     'new_menu': 0},
    {'name': "Trigrams",
     'page': 2,
     'position': 1,
     'action': "Solve Trigrams",
     'new_menu': 0},
    {'name': "Hexagram",
     'page': 2,
     'position': 2,
     'action': "Solve Hexagram",
     'new_menu': 0},
    {'name': "Full",
     'page': 2,
     'position': 3,
     'action': "Solve All Steps",
     'new_menu': 0},
]

OPTION_MENU = [
    {'name': "Help",
     'page': 3,
     'position': 0,
     'action': "Display Help",
     'new_menu': 0},
    {'name': "Controls",
     'page': 3,
     'position': 1,
     'action': "Select Controls",
     'new_menu': 0},
    {'name': "Display",
     'page': 3,
     'position': 2,
     'action': "Select Display",
     'new_menu': 0},
    {'name': "Sounds",
     'page': 3,
     'position': 3,
     'action': "Select Sounds",
     'new_menu': 0},
]

HEXAGRAM_LIST = [
    {'name': "Fu",
     'meaning': "Change (Turning Point)",
     'number': 24,
     'judgement': "Return, Success. going and coming without error. Action brings good fortune",
     'line_1': "Quick return. No remorse. Great good fortune",
     'line_2': "Quiet return. Good fortune.",
     'line_3': "Repeated Return. Danger. No blame.",
     'line_4': "Walking with others, return alone.",
     'line_5': "Noble hearted return. No remorse.",
     'line_6': "Missed chance. Return not possible.",
     'static': ""},
    {'name': "Kuei Mei",
     'meaning': "The Marrying Maiden",
     'number': 54,
     'judgement': "Ill-considered action brings misfortune",
     'line_1': "Acting within your limitations brings good fortune",
     'line_2': "Remain loyal in disappointment.",
     'line_3': "Taking shelter in obligation.",
     'line_4': "Biding timne brings a fruitful union.",
     'line_5': "Accepting marriage below your station bears fruit.",
     'line_6': "Keeping up appearances benefits no-one.",
     'static': "To act now is folly"},
]

class Hexagrams(object):
    def __init__(self, cad, start_item=0):
#
# Working values for testing
#
        self.lines = [blank_space_bits, young_yin_bits, young_yin_bits, old_yang_bits, young_yin_bits,
            old_yang_bits, young_yang_bits, blank_space_bits]
        self.hexagram_number = 54
#
# link to PiFaceCAD library
#
        self.cad = cad
#
    @property
    def display_lines(self):                  # Construct 'Old' Hexagram for storing as a bitmap
        hexagram_image = pifacecad.LCDBitmap(self.lines)
#
# Store the 'Old' Hexagram in Custome Store 0)
#
        self.cad.lcd.store_custom_bitmap(hexagram_index,hexagram_image)
#
# Clear LCD and display Old Hexagram
#
        self.cad.lcd.clear()
        message = "Hexagram " #+ str(self.hexagram_number) + " "
        self.cad.lcd.write(message)
        self.cad.lcd.write_custom_bitmap(hexagram_index)
#
# Process Changing Lines - Old Yang becomes Young Yin and Old Yin becomes Young Yan
#
    def transform(self):
        for itemID in range(len(self.lines)):
            if self.lines[itemID] == old_yang_bits:
                self.lines[itemID] = young_yin_bits
            if self.lines[itemID] == old_yin_bits:
                self.lines[itemID] = young_yang_bits


class DisplayLCD(object):
    def __init__(self, cad, start_item=0):
        self.splash = True
        self.topline = ""
        self.botline = ""
        

class Menus(object):
    def __init__(self, cad, start_item=0):
        self.current_menu_index = start_item
        self.menu_level = 1                     # Top level menu
        self.selected_action = -1               # '-1' identifies no Active selection exists.
        self.active_menu = MAIN_MENU            # Default Menu
        self.cast_method = "Stalks"             # Default Casting Method
        self.waiting = True                     # Denotes that Splash screens are waiting for button press
        self.active = False                     # Denotes that mainprocessing background loop has started
        self.no_quit = True                     # Denotes that User has decided not to abort the program
        self.exit_pending = False               # Denotes that the User has selected the 'Quit' option
        self.paused = False                     # Stops re-entrant code whilst handling interrupts
        self.go_home = True                     # Forces a return to the default top level menu.
        self.cad = cad
#
    @property
    def current_item(self):
        """Returns the current Menu Item."""
        return self.active_menu[self.current_menu_index]
#
    def disabled(self):
        self.cad.lcd.clear()
        self.cad.lcd.set_cursor(1,0)
        self.cad.lcd.write("Button Disabled.")
        self.cad.lcd.set_cursor(2,1)
        self.cad.lcd.write("Press Another.")
#
    def begin_menu(self):
        if not display_lcd.splash:                  # No splash screen following, so set up the menus.
            self.go_home = True                     # Flag restart initiated
            self.current_menu_index = 0             # set up MAIN_MENU Option 0
            self.menu_level = 1
            self.active_menu = MAIN_MENU
            self.update_display()
            self.paused = False                     # Clear button press interrupt handling in progress Flag
#        
    def change_menu(self, new_menu_index):
        if self.waiting:                            # Is Splash screen waiting for button press?
            self.waiting = False                    # Yes, flag button has been pressed
            self.begin_menu()                       # Display opening menu.
    
        elif self.active and not self.paused:       # Else if no pending menu update change menu selection
            """Change the Menu Item."""
            self.current_menu_index = new_menu_index % len(self.active_menu)
            self.update_display()
#
    def confirm(self, event=None):
        if self.waiting:                            # Is Splash screen waiting for button press?
            self.waiting = False                    # Yes, flag button has been pressed
            self.begin_menu()                       # Display opening Menu
#
#   Check if Quit has been requested prior to this invocation.
#
        elif self.exit_pending:                     # If we are here, User has confirmed exit
            self.paused = True                      # Set button press interrupt handling in progress Flag
            self.no_quit = False                    # Tell background routine exit confirmed
            self.cad.lcd.clear()                    # Display quitting message
            self.cad.lcd.set_cursor(4,0)
            self.cad.lcd.write("Quitting.")
            self.cad.lcd.set_cursor(1,1)
            self.cad.lcd.write("Please Wait...")
            self.exit_pending = False               # Flag exit request processing complete
#
#   identify Selection Made
#
        elif self.active and not self.paused:       # Otherwise process default 'Select' action
            self.paused = True                      # Set button press interrupt handling in progress Flag
            self.cad.lcd.clear()                    # Display debugging message
            self.cad.lcd.set_cursor(1,0)
            option_action = self.current_item['action']
            self.cad.lcd.write(option_action)
            self.cad.lcd.set_cursor(1,1)
            self.cad.lcd.write("Selected.")         # End of Debugging message
                                                    # Remember the selection for later.
            self.selected_action = self.current_menu_index
#            self.current_menu_index = 0
#
    def back(self, event=None):
        if self.waiting:                            # Is Splash screen waiting for button press?
            self.waiting = False                    # Yes, flag button has been pressed
            self.begin_menu()                       # Display opening Menu
#
#   Check if Quit has been requested prior to this invocation.
#
        elif self.exit_pending:                     # If we are here, User has confirmed continue
            self.paused = True                      # Set button press interrupt handling in progress Flag
            self.no_quit = True                     # Tell main routine exit aborted
            self.cad.lcd.clear()                    # Display Aborting message
            self.cad.lcd.set_cursor(3,0)
            self.cad.lcd.write("Continuing.")
            self.cad.lcd.set_cursor(1,1)
            self.cad.lcd.write("Please Wait...")
            self.exit_pending = False               # Flag exit request processing complete.
        elif self.active and not self.paused:       # Otherwise process default 'Back' button actions
            self.paused = True                      # Set button press interrupt handling in progress Flag
            if self.menu_level == 2:                # should be 1 or 2, anything other than 2 is treated as a 1.
                self.selected_action = -1           # Clear Active Selection
                self.begin_menu()                   # Display opening Menu
            else:                                   # Send Button Inactive message.
                self.disabled()
#
    def next_item(self, event=None):
        if self.waiting:                        # Is Splash screen waiting for button press?
            self.waiting = False                # Yes, flag button has been pressed
            self.begin_menu()                   # Display opening Menu
#
#   Otherwise if the program running with no menu update or quit request pending,
#   process default 'Next' button actions
#
        elif self.active and not self.paused and not self.exit_pending:     
            self.change_menu(self.current_menu_index + 1)
#
    def previous_item(self, event=None):
        if self.waiting:                        # Is Splash screen waiting for button press?
            self.waiting = False                # Yes, flag button has been pressed
            self.begin_menu()                   # Display opening Menu
#
#   Otherwise if the program running with no menu update or quit request pending,
#   process default 'Previous' button actions
#
        elif self.active and not self.paused and not self.exit_pending:
            self.change_menu(self.current_menu_index - 1)
#
    def update_display(self):
        self.cad.lcd.clear()
        self.update_menu()
        # self.update_playing()
        # self.update_volume()
#
    def update_menu(self):                      # Display options
        """Updates the menu status."""
        display_lcd.botline = self.current_item['action'].ljust(LCD_WIDTH-1)
        display_lcd.topline = str(self.menu_level) + "."
        display_lcd.topline = display_lcd.topline + str(self.current_menu_index + 1) + " "
        display_lcd.topline = display_lcd.topline + self.current_item['name']
        self.cad.lcd.set_cursor(0, 0)
        self.cad.lcd.write(display_lcd.topline)
        self.cad.lcd.set_cursor(1, 1)
        self.cad.lcd.write(display_lcd.botline)
#
    def close(self):
#       Stop attribute only works when running as a service.: disable for now
#       self.stop()     
        self.cad.lcd.clear()
        self.cad.lcd.backlight_off()


def menu_select_switch(event):
    global menus
    menus.change_menu(event.pin_num)


def menu_select_ir(event):
    global menus
    menus.change_menu(int(event.ir_code))


if __name__ == "__main__":
    cad = pifacecad.PiFaceCAD()
    global menus
    menus = Menus(cad)
    hexagrams = Hexagrams(cad)
    display_lcd = DisplayLCD(cad)
    cad.lcd.blink_off()
    cad.lcd.cursor_off()
#
    # listener cannot deactivate itself so we have to wait until it has
    # finished using a barrier.
    global end_barrier
    end_barrier = Barrier(2)
#
    # wait for button presses
    switchlistener = pifacecad.SwitchEventListener(chip=cad)
    for menuid in range(4):
        switchlistener.register(
           menuid, pifacecad.IODIR_ON, menu_select_switch)
    switchlistener.register(4, pifacecad.IODIR_ON, menus.back)
    switchlistener.register(5, pifacecad.IODIR_ON, menus.confirm)
    switchlistener.register(6, pifacecad.IODIR_ON, menus.previous_item)
    switchlistener.register(7, pifacecad.IODIR_ON, menus.next_item)
#
    irlistener = pifacecad.IREventListener(
        prog="i-ching-hexagrams",
        lircrc="/usr/share/doc/scifipi-i-ching/ichinglircrc")
    for i in range(4):
        irlistener.register(str(i), menu_select_ir)
#
    switchlistener.activate()
    try:
        irlistener.activate()
    except lirc.InitError:
        print("Could not initialise IR, running without IR controls.")
        irlistener_activated = False
    else:
        irlistener_activated = True
#
    if "clear" in sys.argv:
        cad.lcd.clear()
        cad.lcd.display_off()
        cad.lcd.backlight_off()
    else:
        #
        #   Store bitmaps for I Ching characters for use later
        #
        cad.lcd.store_custom_bitmap(i_tl_symbol_index,i_tl_symbol)
        cad.lcd.store_custom_bitmap(i_tr_symbol_index,i_tr_symbol)
        cad.lcd.store_custom_bitmap(i_bl_symbol_index,i_bl_symbol)
        cad.lcd.store_custom_bitmap(i_br_symbol_index,i_br_symbol)
        cad.lcd.store_custom_bitmap(ching_tl_symbol_index,ching_tl_symbol)
        cad.lcd.store_custom_bitmap(ching_tr_symbol_index,ching_tr_symbol)
        cad.lcd.store_custom_bitmap(ching_bl_symbol_index,ching_bl_symbol)
        cad.lcd.store_custom_bitmap(ching_br_symbol_index,ching_br_symbol)
        cad.lcd.backlight_on()
        splash_loop()	                # display splash screen until a button is pressed.
        help_splash()                   # Display help on what the buttons are called.
        main_loop()		                # run Main Loop until pressing the 'Back' button clears the menus.active flag.
        sleep(PAUSE_INTERVAL)           # debugging delay.
        cad.lcd.clear()
        cad.lcd.write("Program Stopped")
#
#   Disable Interrup processing
#
        switchlistener.deactivate()
        if irlistener_activated:
            irlistener.deactivate()
    end_barrier.wait()                  # wait for interrupt handlers to stop, then exit
#
    # exit
    menus.close()
#    switchlistener.deactivate()
#    if irlistener_activated:
#        irlistener.deactivate()
