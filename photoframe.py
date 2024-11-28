# [[file:../../../journal.org::*Python script][Python script:1]]
#!/usr/bin/python3

import sys, random, os, json, mimetypes
from datetime import datetime
from os import scandir
from builtins import print as def_print

# Base Qt imports (to be commented)
from PySide6 import Qt, QtCore, QtWidgets, QtGui
# Selective QtImports
from PySide6.QtGui      import QImage, QPixmap, QImageReader, QContextMenuEvent, QAction, QMouseEvent, QWindow
from PySide6.QtWidgets  import QWidget, QLabel, QStatusBar, QMainWindow, QApplication, QMenu, QLineEdit, QGridLayout, QGroupBox, QSpinBox, QCheckBox, QPushButton, QSizePolicy, QFileDialog
from PySide6.QtCore     import QEvent, Qt, QTimer, QSize, QThread, QThreadPool, QRunnable, QObject, QPointF, QDir, Signal

from PIL import Image
from PIL.ImageQt import ImageQt

from time import sleep

def print(text):
    timestamp = datetime.now()
    def_print(timestamp, "\t", text)

debug = True

class Queue():
    def __init__(self):
        self.queue = []
        self.nbItem = 0

    def __iter__(self):
        self.iterPos = 0
        return self

    def __next__(self):
        if self.iterPos < self.nbItem :
            item = self.queue[self.iterPos]
            self.iterPos += 1
            return item
        else:
            raise StopIteration

    def addItem(self, item):
        self.queue.append(item)
        self.nbItem += 1

    def addMultipleItems(self, items: list):
        self.queue.append(items)
        self.nbItem += len(items)

    def popItem(self):
        if self.nbItem < 1:
            raise IndexError("Cannot pop: no more items in queue.")

        self.nbItem -= 1
        return self.queue.pop(0)

    def getNext(self):
        if self.nbItem < 1:
            raise IndexError("Cannot display first item: no more items in queue.")
        return self.queue[0]

    def contains(self, elem):
        return True if elem in self.queue else False

    def getSize(self):
        return self.nbItem

    def getContent(self):
        return self.queue[:]

    def initialize(self, queueContent):
        try:
            assert queueContent is not list
        except AssertionError:
            raise TypeError("Queue can be only initialized with a list.")
        self.queue = queueContent
        self.nbItem = len(queueContent)

    def clear(self):
        self.queue      = []
        self.nbItem     = 0

class WorkerSignals(QObject):
    ready       = Signal()
    addThread   = Signal(str)
    dataReady   = Signal(object)

class MediaHandler(QRunnable):

    def __init__(self, path: str, bulked: bool = False, randomized: bool = False, mainThread: bool = True):
        super().__init__()
        self.path               = path
        self.bulked             = bulked
        self.randomized         = randomized
        self.gatherLayer        = 0
        self.gathering          = False
        self.queue              = Queue()
        self.signals            = WorkerSignals()
        self.mainThread = mainThread
        self.firstScan=False
        if self.mainThread:
            self.firstScan          = True
            self.gatherPhotos(self.path)
            self.firstScan          = False

        self.signals.ready.emit()

    def setPath(self, path: str, clear: bool = False):
        self.path = path
        if clear:
            self.queue.clear()

    def getPath(self):
        return self.path

    def gatherPhotos(self, path: str = None):
        if path is None:
            path = self.path

        curr_dir = ""

        self.gatherLayer += 1
        if self.gatherLayer == 1:
            self.gathering = True

        for elem in scandir(path):
            if not self.gathering:
                return

            if elem.is_dir():
                if self.mainThread:
                    self.gatherPhotos(elem.path)
                else:
                    self.signals.addThread.emit(elem.path)
                if self.firstScan: # cond used to dinstinguish between inital pool of photos and background photo list generation
                    continue
                    break
            else:
                if not self.queue.contains(elem.path):
                    mimestart = mimetypes.guess_type(elem.path)[0]
                    if mimestart != None:
                        mimestart = mimestart.split('/')[0]
                        if not mimestart in ["image"]:
                            continue
                    else:
                        continue
                    self.queue.addItem(elem.path)
                    continue            # To prevent partial scan of the files
                    if self.firstScan and self.queue.getSize() > 50: # cond used to dinstinguish between inital pool of photos and background photo list generation
                        break
        if not self.firstScan:
            if debug:
                print(f"Finished loop! Current folder ({path}) contained {self.queue.nbItem} items.")
            self.signals.dataReady.emit(self.queue)
            self.queue.clear()
            return

        self.gatherLayer -= 1
        if self.gatherLayer == 0:
            if debug and self.firstScan:
                print(f"Finished initial loop! Current folder ({path}) contained {self.queue.nbItem} items.")
            #self.firstScan.emit()

    def run(self):
        self.gatherPhotos(self.path)

    def getNext(self):
        return self.queue.getNext()

    def popItem(self):
        def resetSelf():
            self.queue          = Queue()
            self.firstScan      = True
            self.gatherPhotos(self.path)
            self.firstScan      = False

        try :
            popped = self.queue.popItem()
        except IndexError:
            #self.queue.initialize(self.queueDone.getContent())
            #self.queueDone.clear()
            resetSelf()
            popped = self.queue.popItem()

        if self.queue.nbItem == 0:
            resetSelf()

        #self.queueDone.addItem(popped)
        return popped

class MyTimer(QTimer):
    def __init__(self, connector, interval: int = 1000):
        super().__init__()
        self.setTimerType(Qt.VeryCoarseTimer)
        self.timeout.connect(connector)
        self.setInterval(interval)

# Deprecated, to remove
class MyLabel(QLabel):
    def __init__(self, text: str):
        super().__init__()
        self.setText(text)
        #self.setStyleSheet("background-color: rgba(0, 0, 0, 50%); color : white")

class MyPhoto(QLabel):
    def __init__(self, path: str, windowSize: QSize, hDelta: int):
        super().__init__()
        self.update(path, windowSize, hDelta)

    def update(self, path: str, windowSize: QSize, hDelta: int = 1):
        self.path = path

        im          = Image.open(path)
        exif        = im.getexif()

        try:
            if not exif is None or not len(exif) == 0:
                match exif[274]:
                    case 1:
                        rotationAngle = 0
                        invertXY      = False
                    case 8:
                        rotationAngle = 90
                        invertXY      = True
                    case 3:
                        rotationAngle = 180
                        invertXY      = False
                    case 6:
                        rotationAngle = 270
                        invertXY      = True
                im = im.rotate(rotationAngle, expand = True)
        except KeyError:
            pass

        image       = ImageQt(im)
        self.pixmap = QPixmap.fromImage(image)

        pixmapSize  = self.pixmap.size()
        #screenSize = app.primaryScreen().size()
        screenSize  = windowSize

        imgLargerThanScr = {
            "width": pixmapSize.width() > screenSize.width(),
            "height": pixmapSize.height() > (screenSize.height() - hDelta)
        }

        if imgLargerThanScr["width"] and imgLargerThanScr["height"]:
            if pixmapSize.width() / screenSize.width() > pixmapSize.height() / (screenSize.height() - hDelta) :
                self.pixmap = self.pixmap.scaledToWidth(screenSize.width())
            else:
                self.pixmap = (self.pixmap.scaledToHeight(screenSize.height() - hDelta))

        elif not (not imgLargerThanScr["width"] and not imgLargerThanScr["height"]):
            if imgLargerThanScr["width"]:
                self.pixmap = self.pixmap.scaledToWidth(screenSize.width())
            else:
                self.pixmap = self.pixmap.scaledToHeight(screenSize.height() - hDelta)

        self.setPixmap(self.pixmap)
        self.setAlignment(Qt.AlignCenter)

class MyStatusBar(QStatusBar):
    def __init__(self, counter: int, path: str, display: bool = True):
        super().__init__()
        self.setStyleSheet("background-color: rgba(0, 0, 0, 50%); color : white")
        self.counter    = MyLabel(counter)
        self.sep        = MyLabel("|")
        self.path       = MyLabel(path)
        self.displayed  = display

        if self.displayed:
            self.addPermanentWidget(self.counter)
            self.addPermanentWidget(self.sep)
            self.addPermanentWidget(self.path)

    def updateCounter(self, counter: int):
        self.counter.setText(counter)

    def updatePath(self, path: str):
        self.path.setText(path)

    def toggleDisplay(self):
        self.displayed = not self.displayed

        if self.displayed:
            self.show()
            self.showMessage("Displaying status bar")
        else:
            self.hide()

    def getDisplayStatus(self):
        return self.displayed

    def showMessage(self, message):
        if self.displayed:
            super().showMessage(message, 5000)

class ParametersHolder():
    def __init__(self):
        self.configPath = "./config.json"
        self.paramsType = {
            "displayStatusBar": bool,
            "arePhotoRandomized": bool,
            "arePhotoBulked": bool,
            "photoPath": str,
            "timerInterval": int}
        if os.path.exists(self.configPath):
            self.readParameters()
        else:
            self.setParameters()

    def readParameters(self) -> None:
        with open(self.configPath, 'r') as paramFile:
            self.paramsDict = json.load(paramFile)
        for key in self.paramsDict.keys():
            if key not in self.paramsType.keys():
                self.paramsDict.pop(key)

    def setParameters(self) -> None:
        # Config parameters
        self.paramsDict = {
            "displayStatusBar": True,
            "arePhotoRandomized": False,
            "arePhotoBulked": False,
            "photoPath": "/media/pi/PHOTO_SD/photo/",
            "timerInterval": 5}
        self.writeParameters()

    def writeParameters(self) -> None:
        jsonObject = json.dumps(self.paramsDict, indent=4)
        with open(self.configPath, 'w') as paramFile:
            paramFile.write(jsonObject)

    def updateParameters(self, newParams: dict) -> None:
        for key in newParams:
            assert key in self.paramsDict
            assert self.paramsType[key] is type(newParams[key])

        self.paramsDict = newParams.copy()
        self.writeParameters()

    def updateParameter(self, paramName: str, paramValue) -> None:
        if not paramName in self.paramsDict.keys():
            raise KeyError(f"{paramName} not in self.paramsDict.")

        currType = self.paramsType[paramName]
        if not currType is type(paramValue):
            raise TypeError(f"{paramName} is not of type {currType}")

        self.paramsDict[paramName] = paramValue
        self.writeParameters()

    def getParameter(self, id: str):
        return self.paramsDict[id]

class Parameters(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Paramètres")
        self.parametersHolder = ParametersHolder()

        #self.groupBox            = QGroupBox()
        gridLayout              = QGridLayout()
        # Photo path parameter
        pathLabel               = QLabel("Chemin à scanner :")
        self.pathText           = QLabel(self.parametersHolder.getParameter("photoPath"))
        self.pathB = QPushButton("Changer")
        self.pathB.clicked.connect(self.onChangePathClicked)
        self.pathDialog = QFileDialog(self)
        self.pathDialog.setFileMode(QFileDialog.Directory)
        self.pathDialog.setDirectory(self.parametersHolder.getParameter("photoPath")+"/../")
        gridLayout.addWidget(pathLabel, 0, 0, 1, 1, Qt.AlignRight)
        gridLayout.addWidget(self.pathText, 0, 1, 1, 1, Qt.AlignLeft)
        gridLayout.addWidget(self.pathB, 0, 2, 1, 1, Qt.AlignLeft)
        # Timer parameter
        timerLabel              = QLabel("Durée d'affichage par photo :")
        self.timerValue         = QSpinBox()
        self.timerValue.setRange(1, 60)
        self.timerValue.setSuffix("sec")
        self.timerValue.setValue(self.parametersHolder.getParameter("timerInterval"))
        gridLayout.addWidget(timerLabel, 1, 0, 1, 1, Qt.AlignRight)
        gridLayout.addWidget(self.timerValue, 1, 1, 1, 4, Qt.AlignLeft)
        # Checkbox parameter parameter
        self.statusBarDisplay   = QCheckBox("Afficher la barre de statut.")
        statusValue = Qt.Checked if self.parametersHolder.getParameter("displayStatusBar") else Qt.Unchecked
        self.statusBarDisplay.setCheckState(statusValue)

        self.randomize          = QCheckBox("Mélanger les photos.")
        randomizeStatus = Qt.Checked if self.parametersHolder.getParameter("arePhotoRandomized") else Qt.Unchecked
        self.randomize.setCheckState(randomizeStatus)
        self.bulkedPhotos       = QCheckBox("Grouper les photos par dossier.")
        bulkedStatus = Qt.Checked if self.parametersHolder.getParameter("arePhotoBulked") else Qt.Unchecked
        self.bulkedPhotos.setCheckState(bulkedStatus)
        gridLayout.addWidget(self.statusBarDisplay, 2, 0, 1, 5, Qt.AlignCenter)
        gridLayout.addWidget(self.randomize, 4, 0, 1, 5, Qt.AlignCenter)
        gridLayout.addWidget(self.bulkedPhotos, 5, 0, 1, 5, Qt.AlignCenter)
        # Cancel and validation buttons
        self.applyB             = QPushButton("Enregistrer")
        cancelB                 = QPushButton("Annuler")
        gridLayout.addWidget(self.applyB, 6, 1, 1, 1, Qt.AlignCenter)
        gridLayout.addWidget(cancelB,  6, 3, 1, 1, Qt.AlignCenter)

        upcomingLabel           = QLabel("En cours de développement:")
        gridLayout.addWidget(upcomingLabel, 3, 0, 1, 5, Qt.AlignLeft)


        self.setLayout(gridLayout)
        self.applyB.clicked.connect(self.onApplyClicked)
        cancelB.clicked.connect(self.onCancelClicked)

    def onChangePathClicked(self):
        if self.pathDialog.exec():
            self.pathText.setText(self.pathDialog.selectedFiles()[0])

    def onApplyClicked(self):
        newParams = {
            "displayStatusBar": self.statusBarDisplay.isChecked(),
            "arePhotoRandomized": self.randomize.isChecked(),
            "arePhotoBulked": self.bulkedPhotos.isChecked(),
            "photoPath": self.pathText.text(),
            "timerInterval": self.timerValue.value()
        }
        self.parametersHolder.updateParameters(newParams)
        self.destroy()

    def onCancelClicked(self):
        self.destroy()

class PhotoFrame(QMainWindow):
    '''
    This window will display the photos as well as a status bar (if the user requires it)
    From it a contextual menu is accessible and allows the user to customize the application, refresh photos or exit the application.
    '''
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Cadre Photo")

        QImageReader.supportedImageFormats()

        # Config parameters
        myParams = ParametersHolder()
        if not os.path.isdir(myParams.getParameter("photoPath")):
            tmpParametersWindow = Parameters()
            if tmpParametersWindow.pathDialog.exec():
                myParams.updateParameter("photoPath", tmpParametersWindow.pathDialog.selectedFiles()[0])

        # Set backround to black
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.black)
        self.setPalette(p)

        # Define contextMenu
        self.menu = QMenu()
        self.scan       = QAction("Scanner les photos")
        self.parameters = QAction("Paramètres")
        self.close_app  = QAction("Quitter")
        self.menu.addAction(self.scan)
        self.menu.addAction(self.parameters)
        self.menu.addAction(self.close_app)
        #self.scan.triggered.connect()
        self.parameters.triggered.connect(self.openParameters)
        self.close_app.triggered.connect(self.close)

        # Define timer for slideshow
        self.timerPhoto = MyTimer(self.setImage, myParams.getParameter("timerInterval") * 1000)
        # Define timer for time counter
        self.timerCounter = MyTimer(self.updateCounter, 1000)
        # Initialize photo gatherer & queue
        self.mediaHandler = MediaHandler(myParams.getParameter("photoPath"))

        # Initilalize thread
        self.threadShouldRun            = True
        self.workerPool                 = QThreadPool()
        self.workerList                 = []
        self.workerPoolScannedPathList  = []

        # Initialize widgets
        counter   = str(myParams.getParameter("timerInterval"))
        self.statusBar = MyStatusBar(counter, self.mediaHandler.getNext(), myParams.getParameter("displayStatusBar"))

        photo_height_delta = self.statusBar.size().height() if myParams.getParameter("displayStatusBar") else 0
        self.photo = MyPhoto(self.mediaHandler.getNext(), self.size(), 1)

        # Initialize counters
        self.timerPhoto.start()
        self.timerCounter.start()

        # Connect & ready thread
        self.onOrderThreadCreation(myParams.getParameter("photoPath"))
        #self.destroyed.connect(self.stopThread)

    def resizeEvent(self, event: QEvent):
        if event.type() == QEvent.Resize:
            self.setStatusBar(self.statusBar)
            self.setCentralWidget(self.photo)
            self.setImage()
        super().resizeEvent(event)

    def updateCounter(self):
        self.statusBar.updateCounter(str(round(self.timerPhoto.remainingTime()/1000)))

    def setImage(self):
        path = self.mediaHandler.popItem()
        self.photo.update(path, self.size(), self.statusBar.size().height())
        self.statusBar.updatePath(path)

    def onParametersUpdated(self):
        parameters = ParametersHolder()

        if self.timerPhoto.interval() != parameters.getParameter("timerInterval"):
            self.timerPhoto.setInterval(parameters.getParameter("timerInterval") * 1000)
            interval = parameters.getParameter("timerInterval")
            self.statusBar.showMessage(f"Updating photo persistence to {interval} seconds")

        if self.mediaHandler.getPath() != parameters.getParameter("photoPath"):
            self.mediaHandler.setPath(parameters.getParameter("photoPath"), True)
            path = parameters.getParameter("photoPath")
            self.statusBar.showMessage(f"Setting photo path to {path}")

        if self.statusBar.getDisplayStatus() != parameters.getParameter("displayStatusBar"):
            self.statusBar.toggleDisplay()

    def openContextMenu(self, pos: QPointF):
        self.menu.popup(pos.toPoint())

    def openParameters(self):
        self.parametersWindow = Parameters()
        self.parametersWindow.applyB.clicked.connect(self.onParametersUpdated)
        self.parametersWindow.show()

    def keyPressEvent(self, event: QEvent):
        if event.key() == Qt.Key_Escape:
            self.showNormal()
            self.statusBar.showMessage("Exited FullScreen")
        elif event.key() == Qt.Key_F:
            self.showFullScreen()
            self.statusBar.showMessage("Entered FullScreen")
        elif event.key() != Qt.Key_F or event.key() != Qt.Key_Escape:
            self.statusBar.showMessage("Use other key (F for fullscreen, ESC for maximized or right clic for menu)")
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() ==  Qt.MouseButton.RightButton:
            self.statusBar.showMessage("Accessing contextual menu")
            self.openContextMenu(event.position())
        event.accept()

    def closeEvent(self, event):
        self.mediaHandler.gathering = False
        self.workerThread.quit()
        #self.workerThread.wait()

    def onOrderThreadCreation(self, path: str):
        if path in self.workerPoolScannedPathList:
            return

        self.workerPoolScannedPathList.append(path)
        self.workerList.append(MediaHandler(path=path, mainThread = False))
        self.workerList[-1].signals.dataReady[Queue].connect(self.onWorkerDataReady)
        self.workerList[-1].signals.addThread[str].connect(self.onOrderThreadCreation)
        #self.workerList[-1].
        self.workerPool.start(self.workerList[-1])
        print(f"New thread added for a total of {len(self.workerList)}.")

    def onWorkerDataReady(self, queue: Queue):
        # Add control of duplicate items
        trimmedQueue = Queue()
        for item in queue:
            if not self.mediaHandler.queue.contains(item):
                trimmedQueue.addItem(item)
        self.mediaHandler.queue.addMultipleItems(trimmedQueue.queue)
        print(f"Added {trimmedQueue.nbItem} items to the current queue which has now {self.mediaHandler.queue.nbItem} items.")

    # Ex of slot
    @QtCore.Slot()
    def magic(self):
        self.text.setText(random.choice(self.hello))

# Main program
if __name__ == "__main__":
    print("Start app.")
    app = QApplication([])

    widget = PhotoFrame()
    #widget.show()
    widget.showFullScreen()

    sys.exit(app.exec())
# Python script:1 ends here
