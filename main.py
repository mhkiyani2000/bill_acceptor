from time import time
from kivy.app import App
from os.path import dirname, join
from kivy.lang import Builder
from kivy.properties import NumericProperty, StringProperty, BooleanProperty,ListProperty
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.uix.screenmanager import Screen
import sys
from threading import Thread
import serial, time, binascii


### Globals ###
#Change this value to modify polling rate. Currently 100 ms
POLL_RATE = 0.15
global master_proc
global aapp


class Host(object):
    """
    An RS-232 master interface. A master operates with a RS-232
    slave for the purpose of accepting money in exchange for goods or services.
    """
    state_dict = {1:"Idling ", 2:"Accepting ", 4:"Escrowed ", 8:"Stacking ",
                  16:"Stacked ", 32:"Returning", 64:"Returned",
                  17:"Stacked Idling ", 65:"Returned Idling "}
    event_dict = {0:"", 1:"Cheated ", 2:"Rejected ", 4:"Jammed ", 8:"Full "}

    def __init__(self):
        # Set to False to kill
        self.running = True
        self.bill_count = bytearray([0, 0, 0, 0, 0, 0, 0, 0])

        self.ack = 0
        self.credit = 0
        self.last_state = ''
        self.escrowed = False
        self.verbose = False

        # Background worker thread
        self._serial_thread = None

    def start(self, portname):
        """
        Start Host in a non-daemon thread

        Args:
            portname -- string name of the port to open and listen on

        Returns:
            None

        """
        self._serial_thread = Thread(target=self._serial_runner,
                                     args=(portname,))
        # Per https://docs.python.org/2/library/threading.html#thread-objects
        # 16.2.1: Daemon threads are abruptly stopped, set to false for proper
        # release of resources (i.e. our comm port)
        self._serial_thread.daemon = False
        self._serial_thread.start()

    def stop(self):
        """
        Blocks until Host can safely be stopped

        Args:
            None

        Returns:
            None
        """
        self.running = False
        self._serial_thread.join()

    def parse_cmd(self, cmd):
        """
        Applies the given command to modify the state/event of
        this Host

        Args:
            cmd -- string arg

        Returns:
            Int -- 0 if okay, 1 to exit, 2 to quit
        """
        if cmd == 'Q':
            return 1
        if cmd == '?' or cmd is 'H':
            return 2

        if cmd == 'V':
            self.verbose = not self.verbose

        return 0

    def _serial_runner(self, portname):
        """
        Polls and interprets message from slave acceptor over serial port
        using global poll rate

        Args:
            portname -- string portname to open

        Returns:
            None
        """

        ser = serial.Serial(
            port=portname,
            baudrate=9600,
            bytesize=serial.SEVENBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE
        )

        while ser.isOpen() and self.running:

            # basic message   0      1     2      3      4      5     6         7
            #               start, len,  ack, bills,escrow,resv'd,  end, checksum
            msg = bytearray([0x02, 0x08, 0x10, 0x7F,  0x00,  0x00, 0x03,     0x00])

            msg[2] = 0x10 | self.ack
            self.ack ^= 1

            # If escrow, stack the note
            if self.escrowed:
                msg[4] |= 0x20

            # Set the checksum
            for byte in xrange(1, 6):
                msg[7] ^= msg[byte]


            ser.write(msg)
            time.sleep(0.1)

            out = ''
            while ser.inWaiting() > 0:
                out += ser.read(1)
            if out == '':
                continue

            # With the exception of Stacked and Returned, only we can
            # only be in one state at once
            try:
                status = Host.state_dict[ord(out[3])]
            except KeyError:
                status = ''
                print "unknown state dic key {:d}".format(ord(out[3]))

            self.escrowed = ord(out[3]) & 4

            # If there is no match, we get an empty string
            try:
                status += Host.event_dict[ord(out[4]) & 1]
                status += Host.event_dict[ord(out[4]) & 2]
                status += Host.event_dict[ord(out[4]) & 4]
                status += Host.event_dict[ord(out[4]) & 8]
            except KeyError:
                print "unknown state dic key {:d}".format(ord(out[4]))

            if ord(out[4]) & 0x10 != 0x10:
                status += " CASSETTE MISSING"

            # Only update the status if it has changed
            if self.last_state != status:
                print 'Acceptor status:', status
                self.last_state = status

            if self.verbose:
                print ", ".join("0x{:02x}".format(ord(c)) for c in out)

            # Print credit(s)
            credit = (ord(out[5]) & 0x38) >> 3

            if credit != 0:
                if ord(out[3]) & 0x10:
                    print "Bill credited: Bill#", credit
                    if credit == 1:
                        moneyamount = 1
                    if credit == 2:
                        moneyamount = 2
                    if credit == 3:
                        moneyamount = 5
                    if credit == 4:
                        moneyamount = 10
                    if credit == 5:
                        moneyamount = 20
                    if credit == 6:
                        moneyamount = 50
                    if credit == 7:
                        moneyamount = 100

                    global aapp
                    aapp.set_billamount(moneyamount)

                    self.bill_count[credit] += 1
                    print "Acceptor now holds: {:s}".format(
                        binascii.hexlify(self.bill_count))

            time.sleep(POLL_RATE)

        print "port closed"
        ser.close()

### APEX RS232 Main  Routine ###
def apex_rs232_proc_start(portname):
    print "Starting APEX RS-232 Master on port {:s}".format(portname)
    global master_proc
    master_proc = Host()
    master_proc.start(portname)

def apex_rs232_proc_stop():
    global master_proc
    master_proc.stop()
    master_proc = 0

class BillAcceptorScreen(Screen):
    fullscreen = BooleanProperty(False)

    def add_widget(self, *args):
        if 'content' in self.ids:
            return self.ids.content.add_widget(*args)
        return super(BillAcceptorScreen, self).add_widget(*args)

class BillAcceptorApp(App):

    index = NumericProperty(-1)
    current_title = StringProperty()
    time = NumericProperty(0)
    show_sourcecode = BooleanProperty(False)
    sourcecode = StringProperty()
    screen_names = ListProperty([])
    hierarchy = ListProperty([])
    strbillamount = StringProperty('0')
    billamount = 0
    phonenumber = StringProperty('Phone Number')

    def build(self):
        self.title = 'Bill Acceptor'
        #Clock.schedule_interval(self._update_clock, 1 / 60.)
        self.screens = {}

        self.available_screens = sorted([
            'step1', 'step2', 'step3', 'step4'])
        self.screen_names = self.available_screens
        curdir = dirname(__file__)
        self.available_screens = [join(curdir, 'data', 'screens',
            '{}.kv'.format(fn)) for fn in self.available_screens]
        self.go_next_screen()

    def on_pause(self):
        return True

    def on_resume(self):
        pass

    def go_previous_screen(self):
        self.index = (self.index - 1) % len(self.available_screens)
        screen = self.load_screen(self.index)
        sm = self.root.ids.sm
        sm.switch_to(screen, direction='right')
        self.current_title = screen.name

    def set_billamount(self, amount):
        tmp = self.billamount + amount
        self.strbillamount = str(tmp)
        self.billamount = tmp

    def go_next_screen(self):
        self.index = (self.index + 1) % len(self.available_screens)
        screen = self.load_screen(self.index)

        sm = self.root.ids.sm
        sm.switch_to(screen, direction='left')
        self.current_title = screen.name

        if self.index == 2:
            apex_rs232_proc_start('COM3')

        if self.index == 3:
            apex_rs232_proc_stop()

    def go_screen(self, idx):
        self.index = idx
        self.root.ids.sm.switch_to(self.load_screen(idx), direction='left')

    def go_hierarchy_previous(self):
        ahr = self.hierarchy
        if len(ahr) == 1:
            return
        if ahr:
            ahr.pop()
        if ahr:
            idx = ahr.pop()
            self.go_screen(idx)

    def load_screen(self, index):
        if index in self.screens:
            return self.screens[index]
        screen = Builder.load_file(self.available_screens[index].lower())
        self.screens[index] = screen
        return screen

    def add_phonenumber(self, num):
        if self.phonenumber == 'Phone Number':
            self.phonenumber = ''

        self.phonenumber = self.phonenumber + str(num)

    def delete_phonenumber(self):
        self.phonenumber = self.phonenumber[:-1]

    def _update_clock(self, dt):
        self.time = time()

if __name__ == '__main__':
    global aapp
    aapp = BillAcceptorApp()
    aapp.run()

