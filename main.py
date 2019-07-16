import sys
import os
import asyncio
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


class MainWindow(QMainWindow):

    new_log_line = pyqtSignal(str, name='new_log_line')

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
                    my_filter=lambda s,kw=kw: kw in s))
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
        self.is_fetching = False

        self.resize(2000, 1000)

        # we set auto-start
        self.on_start_log()

    @staticmethod
    def make_slot(tv, my_filter):
        @pyqtSlot(str)
        def foo(sss):
            if my_filter(sss):
                tv.appendPlainText(sss)

        return foo

    def on_clear_log(self):

        def clear_log():
            os.system('adb logcat -c')
            # TODO: clear all sub widget's content

        if self.is_fetching:
            self.on_stop_log()
            clear_log()
            self.on_start_log()
        else:
            clear_log()

    def on_stop_log(self):
        self.start_log_action.setEnabled(True)
        self.stop_log_action.setEnabled(False)
        self.statusBar().showMessage('Stopped.')
        self.is_fetching = False

    @asyncSlot()
    async def on_start_log(self):
        self.start_log_action.setEnabled(False)
        self.stop_log_action.setEnabled(True)
        self.statusBar().showMessage('Fetching...')
        self.is_fetching = True

        proc = await asyncio.create_subprocess_shell('adb logcat -v time', stdout=asyncio.subprocess.PIPE)
        try:
            while self.is_fetching:
                data = await proc.stdout.readline()
                try:
                    line = data.decode().rstrip()
                except Exception as e:
                    line = data.decode('ISO-8859-1').rstrip()
                self.new_log_line.emit(line)
        except Exception as exc:
            print(exc)
            self.statusBar().showMessage('Error: {}'.format(exc))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    mainWindow = MainWindow()
    mainWindow.show()

    with loop:
        sys.exit(loop.run_forever())
