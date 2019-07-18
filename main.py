import sys
import os
import asyncio
from collections import namedtuple
from asyncqt import QEventLoop, asyncSlot, asyncClose
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QPlainTextEdit,
    QScrollBar,
    QStatusBar,
    QVBoxLayout,
    QMdiArea,
    QAction,
    QMenuBar,
    QToolBar,
    QMainWindow)
from PyQt5.QtCore import (QObject, pyqtSignal, pyqtSlot)

loop = None

LOG_LINE = namedtuple('LOG_LINE', ['date', 'time', 'pid', 'pname', 'tid', 'level', 'msg'])


class MainWindow(QMainWindow):

    new_log_line = pyqtSignal(object, name='new_log_line')

    def add_mdi_widget(self, my_title, my_filter):
        wdg1 = QWidget()
        wdg1.setWindowTitle(my_title)
        wdg1.setLayout(QVBoxLayout())
        layout = wdg1.layout()

        te = QPlainTextEdit('', self)
        layout.addWidget(te)

        def on_scroll_to_end():
            x = te.verticalScrollBar()
            # trick to tell PyCharm the type info
            assert isinstance(x, QScrollBar)
            x.setValue(x.maximum())

        btn_scroll = QPushButton('ScrollToButtom', self)
        btn_scroll.clicked.connect(on_scroll_to_end)
        layout.addWidget(btn_scroll)

        self.new_log_line.connect(self.make_slot(te, my_filter))

        # TODO: using parent's width, get rid of hard coded width
        wdg1.setFixedWidth(1800)

        return wdg1

    def __init__(self):
        super().__init__()

        # MDI
        self.mdiArea = QMdiArea(self)
        for kw in ('ARC_SN_Process', 'mCaptureStartTime'):
            self.mdiArea.addSubWindow(
                self.add_mdi_widget(
                    my_title=kw,
                    my_filter=lambda s, kw=kw: kw in s.msg))
        self.setCentralWidget(self.mdiArea)

        # TOOL BAR
        self.start_log_action = QAction('Start', self)
        self.start_log_action.triggered.connect(self.on_start_log)

        self.stop_log_action = QAction('Stop', self)
        self.stop_log_action.triggered.connect(self.on_stop_log)
        self.stop_log_action.setEnabled(False)

        self.clear_log_action = QAction('Clear', self)
        self.clear_log_action.triggered.connect(self.on_clear_log)

        toolbar = QToolBar()
        toolbar.addAction(self.start_log_action)
        toolbar.addAction(self.stop_log_action)
        toolbar.addAction(self.clear_log_action)
        self.addToolBar(toolbar)

        # OTHERS
        self.resize(2000, 1000)

        self.log_task = None

        # we set auto-start
        self.on_start_log()

        global loop
        loop.create_task(self.get_pid())

        self.pid_name_dict = dict()

    @staticmethod
    def make_slot(tv, my_filter):
        @pyqtSlot(str)
        def foo(sss):
            if my_filter(sss):
                tv.appendPlainText(sss.msg)  # TODO: more content to add

        return foo

    def on_clear_log(self):

        def clear_log():
            os.system('adb logcat -c')
            # TODO: clear all sub widget's content

        if self.log_task:
            self.on_stop_log()
            clear_log()
            self.on_start_log()
        else:
            clear_log()

    def on_stop_log(self):
        self.log_task.cancel()
        self.log_task = None

        self.start_log_action.setEnabled(True)
        self.stop_log_action.setEnabled(False)
        self.statusBar().showMessage('Stopped.')

    def on_start_log(self):
        self.start_log_action.setEnabled(False)
        self.stop_log_action.setEnabled(True)
        self.statusBar().showMessage('Fetching...')
        global loop
        self.log_task = loop.create_task(self.get_logs())

    async def get_logs(self):
        proc = await asyncio.create_subprocess_shell('adb logcat -v threadtime', stdout=asyncio.subprocess.PIPE)
        try:
            while True:
                data = await proc.stdout.readline()
                try:
                    line = data.decode().rstrip()
                except Exception as e:
                    line = data.decode('ISO-8859-1').rstrip()
                if not line:
                    continue
                if line[0] == '-':  # TODO: more reliable way
                    continue
                line = line.split(None, 5)
                pname = self.get_pname(line[2])
                line = LOG_LINE(date=line[0], time=line[1], pid=line[2], tid=line[3], level=line[4], msg=line[5], pname=pname)
                self.new_log_line.emit(line)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(exc)
            self.statusBar().showMessage('Error: {}'.format(exc))

    async def get_pid(self):
        try:
            while True:
                data = os.popen('adb shell ps').read()
                lines = data.split('\n')
                fields = lines[0].split()
                assert fields[1] == 'PID'
                assert fields[-1] == 'NAME'

                fields = [line.split() for line in lines[1:]]
                self.pid_name_dict = dict([(field[1], field[-1])
                                           for field in fields if field])

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(exc)
            self.statusBar().showMessage('Error: {}'.format(exc))

    def get_pname(self, pid):
        return self.pid_name_dict[pid] if pid in self.pid_name_dict else None


def main():
    global loop

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    mainWindow = MainWindow()
    mainWindow.show()

    with loop:
        sys.exit(loop.run_forever())


if __name__ == '__main__':
    main()
