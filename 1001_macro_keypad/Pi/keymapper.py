import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from pynput.keyboard import Listener, Key, KeyCode
import json
import os
KMK_KEYCODES = {
    "A": 0x04,
    "B": 0x05,
    "C": 0x06,
    "D": 0x07,
    "E": 0x08,
    "F": 0x09,
    "G": 0x0A,
    "H": 0x0B,
    "I": 0x0C,
    "J": 0x0D,
    "K": 0x0E,
    "L": 0x0F,
    "M": 0x10,
    "N": 0x11,
    "O": 0x12,
    "P": 0x13,
    "Q": 0x14,
    "R": 0x15,
    "S": 0x16,
    "T": 0x17,
    "U": 0x18,
    "V": 0x19,
    "W": 0x1A,
    "X": 0x1B,
    "Y": 0x1C,
    "Z": 0x1D,
    "1": 0x1E,
    "2": 0x1F,
    "3": 0x20,
    "4": 0x21,
    "5": 0x22,
    "6": 0x23,
    "7": 0x24,
    "8": 0x25,
    "9": 0x26,
    "0": 0x27,
    "ENTER": 0x28,
    "ESC": 0x29,
    "BACKSPACE": 0x2A,
    "TAB": 0x2B,
    "SPACE": 0x2C,
    "CTRL": 0xE0,
    "SHIFT": 0xE1,
    "ALT": 0xE2,
    "GUI": 0xE3,
}


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        self.boardPath = ""
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(900, 700)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        
        self.gridLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.gridLayoutWidget.setGeometry(QtCore.QRect(40, 20, 571, 422))
        self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.gridLayout = QtWidgets.QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setHorizontalSpacing(0)
        self.gridLayout.setVerticalSpacing(40)
        self.gridLayout.setObjectName("gridLayout1")

        # 반복문으로 레이아웃과 위젯 생성
        self.labels = []
        self.buttons = []
        self.create_layout_and_widgets(12, 0, self.gridLayout)  # 0부터 시작하는 인덱스
        
        self.horizontalLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.horizontalLayoutWidget.setGeometry(QtCore.QRect(630, 470, 271, 121))
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setSpacing(10)

        self.create_layout_and_widgets(2,12, self.horizontalLayout)

        self.buttonWidget = QtWidgets.QWidget(self.centralwidget)
        self.buttonWidget.setGeometry(QtCore.QRect(100, 550, 400, 100))
        self.pathLabel = QtWidgets.QLabel(self.buttonWidget)
        self.pathLabel.setText("Board Path:")
        self.setBoardPathButton = QtWidgets.QPushButton(self.buttonWidget)
        self.setBoardPathButton.setObjectName("setBoardPathButton")
        self.setBoardPathButton.setText("Set Board Path")
        
        
        self.printButton = QtWidgets.QPushButton(self.buttonWidget)
        self.printButton.setObjectName("printButton")
        self.printButton.setText("Apply to KEYPAD")
        self.buttonLayout = QtWidgets.QHBoxLayout(self.buttonWidget)
        self.buttonLayout.addWidget(self.setBoardPathButton)
        self.buttonLayout.addWidget(self.printButton)
        self.printButton.clicked.connect(self.on_print_clicked)
        self.setBoardPathButton.clicked.connect(self.on_set_board_path_clicked)

        self.labelLayer = QtWidgets.QLabel(self.centralwidget)
        self.labelLayer.setGeometry(QtCore.QRect(760, 20, 111, 31))
        font = QtGui.QFont()
        font.setFamily("Malgun Gothic")
        font.setPointSize(13)
        self.labelLayer.setFont(font)
        self.labelLayer.setObjectName("labelLayer")
        self.labelLayer.setText("Layer Index:")

        self.labelLayerIdx = QtWidgets.QLabel(self.centralwidget)
        self.labelLayerIdx.setGeometry(QtCore.QRect(840, 50, 56, 31))
        self.labelLayerIdx.setText("0")
        font = QtGui.QFont()
        font.setFamily("Malgun Gothic")
        font.setPointSize(20)
        font.setBold(True)
        font.setWeight(75)
        self.labelLayerIdx.setFont(font)
        self.labelLayerIdx.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.labelLayerIdx.setObjectName("labelLayerIdx")

        self.layerUpButton = QtWidgets.QPushButton(self.centralwidget)
        self.layerUpButton.setGeometry(QtCore.QRect(820, 100, 50, 30))
        self.layerUpButton.setText("+")
        self.layerUpButton.clicked.connect(self.increase_layer)

        self.layerDownButton = QtWidgets.QPushButton(self.centralwidget)
        self.layerDownButton.setGeometry(QtCore.QRect(760, 100, 50, 30))
        self.layerDownButton.setText("-")
        self.layerDownButton.clicked.connect(self.decrease_layer)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.actionNew = QtWidgets.QAction(MainWindow)
        self.actionNew.setObjectName("actionNew")
        self.actionLoad = QtWidgets.QAction(MainWindow)
        self.actionLoad.setObjectName("actionLoad")
        self.actionSave = QtWidgets.QAction(MainWindow)
        self.actionSave.setObjectName("actionSave")
        self.actionExit = QtWidgets.QAction(MainWindow)
        self.actionExit.setObjectName("actionExit")
        self.menuFile.addAction(self.actionNew)
        self.menuFile.addAction(self.actionLoad)
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionExit)
        self.menubar.addAction(self.menuFile.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        
        self.initialize_layers()  # 레이어 초기화
        self.current_layer = 0

    def initialize_layers(self):
        self.layers = [["NO"] * 14 for _ in range(6)]  # 최대 6개의 레이어

    def increase_layer(self):
        """레이어 인덱스를 증가시키는 함수"""
        if self.current_layer < 5:
            self.current_layer += 1
            self.labelLayerIdx.setText(str(self.current_layer))
        self.refresh_keymaps()
        

    def decrease_layer(self):
        """레이어 인덱스를 감소시키는 함수"""
        if self.current_layer > 0:
            self.current_layer -= 1
            self.labelLayerIdx.setText(str(self.current_layer))
        self.refresh_keymaps()

    def refresh_keymaps(self):
        """키맵을 새로 고치는 함수"""
        for i in range(14):
            self.labels[i].setText(self.layers[self.current_layer][i])

    def create_layout_and_widgets(self, ranges, addVal, _layout):
        for i in range(ranges):  # 12개의 그룹 생성
            layout = QtWidgets.QVBoxLayout()
            layout.setObjectName(f"BindingGroup{i + addVal}")

            label = QtWidgets.QLabel(self.gridLayoutWidget)
            font = QtGui.QFont()
            font.setFamily("맑은 고딕")
            font.setPointSize(12)
            font.setKerning(True)
            label.setFont(font)
            label.setObjectName(f"label_{i + addVal}")
            label.setText("NO")
            layout.addWidget(label)
            self.labels.append(label)

            button = QtWidgets.QPushButton(self.gridLayoutWidget)
            button.setObjectName(f"pushButton_{i + addVal}")
            button.setText("Assign Key")
            layout.addWidget(button)
            self.buttons.append(button)
            button.clicked.connect(lambda _, idx=i + addVal: self.on_button_clicked(idx))  # 버튼 클릭 시 이벤트 연결

            macroButton = QtWidgets.QPushButton(self.gridLayoutWidget)
            macroButton.setObjectName(f"macroButton_{i + addVal}")
            macroButton.setText("Assign Macro")
            layout.addWidget(macroButton)
            macroButton.clicked.connect(lambda _, idx=i + addVal: self.on_macro_button_clicked(idx))  # 매크로 버튼 클릭 시 이벤트 연결

            # 그리드 레이아웃에 추가 (4x3 기준)
            row = i // 4  # 3열 기준으로 행 계산
            col = i % 4   # 열 계산
            if _layout == self.gridLayout:
                _layout.addLayout(layout, row, col, 1, 1)
            elif _layout == self.horizontalLayout:
                _layout.addLayout(layout)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "KeyMapper"))
        self.menuFile.setTitle(_translate("MainWindow", "File"))
        self.actionNew.setText(_translate("MainWindow", "New"))
        self.actionNew.triggered.connect(self.onActionNew)  # New 액션에 이벤트 연결
        self.actionNew.setShortcut(_translate("MainWindow", "Ctrl+N"))
        self.actionLoad.setText(_translate("MainWindow", "Load"))
        self.actionLoad.triggered.connect(self.onActionLoad)  # Load 액션에 이벤트 연결
        self.actionLoad.setShortcut(_translate("MainWindow", "Ctrl+L"))
        self.actionSave.setText(_translate("MainWindow", "Save"))
        self.actionSave.triggered.connect(self.onActionSave)  # Save 액션에 이벤트 연결
        self.actionSave.setShortcut(_translate("MainWindow", "Ctrl+S"))
        self.actionExit.setText(_translate("MainWindow", "Exit"))
        self.actionExit.triggered.connect(QtWidgets.qApp.quit)  # Exit 액션에 이벤트 연결
        self.actionExit.setShortcut(_translate("MainWindow", "Alt+F4"))

    def onActionLoad(self):
        """JSON 파일에서 키맵을 로드하는 함수"""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Load Keymaps", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'r') as f:
                self.layers = json.load(f)
            self.refresh_keymaps()  # 키맵 새로 고침 

    def onActionSave(self):
        """현재 레이어의 키맵을 JSON 파일로 저장하는 함수"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(None, "Save Keymaps", "", "JSON Files (*.json)")
        if filename:
            with open(filename, 'w') as f:
                json.dump(self.layers, f, indent=4)

    def onActionNew(self):
        """새로운 키맵을 생성하는 함수"""
        self.layers = [["NO"] * 14 for _ in range(6)]
        self.refresh_keymaps()  # 키맵 새로 고침
        self.labelLayerIdx.setText("0")  # 레이어 인덱스 초기화
        self.current_layer = 0  # 현재 레이어 초기화


    def on_button_clicked(self, index):
        print(f"Waiting for key input for button {index}...")

        if len(self.layers[self.current_layer]) <= index:
            # 현재 레이어의 리스트 크기를 확장
            self.layers[self.current_layer].extend(["UnAssigned"] * (index - len(self.layers[self.current_layer]) + 1))

        # 데이터 업데이트
        self.layers[self.current_layer][index] = f"Key {index}"
        print(f"Updated layer {self.current_layer}: {self.layers[self.current_layer]}")

        # UI 업데이트
        self.labels[index].setText(self.layers[self.current_layer][index])
        pressed_keys = set()

        # 특수키 매핑
        SPECIAL_KEYS = {
            "CTRL_L": "CTRL",
            "CTRL_R": "CTRL",
            "SHIFT": "SHIFT",
            "SHIFT_L": "SHIFT",
            "SHIFT_R": "SHIFT",
            "ALT": "ALT",
            "ALT_L": "ALT",
            "ALT_R": "ALT",
            "CMD": "GUI",  # 윈도우 키를 GUI로 매핑
            "CMD_L": "GUI",
            "CMD_R": "GUI",
        }

        # ASCII 제어 문자 매핑
        ASCII_CONTROL_MAP = {
            chr(i): f"{chr(i + 64)}" for i in range(1, 27)  # \x01 to \x1A -> CTRL+A to CTRL+Z
        }

        def on_press(key):
            try:
                # 키 이름 가져오기
                if isinstance(key, Key):  # 특수키 처리
                    keyname = str(key).replace("Key.", "").upper()
                    keyname = SPECIAL_KEYS.get(keyname, keyname)  # 특수키 매핑
                elif hasattr(key, 'char') and key.char:  # 일반 키 처리
                    if key.char in ASCII_CONTROL_MAP:  # ASCII 제어 문자 처리
                        keyname = ASCII_CONTROL_MAP[key.char]
                    else:
                        keyname = key.char.upper()
                else:
                    keyname = str(key).upper()

                print(f"Key pressed: {keyname}")

                # 중복된 특수키가 pressed_keys에 추가되지 않도록 처리
                if keyname in pressed_keys:
                    return

                pressed_keys.add(keyname)

                # 특수키만 눌린 경우, 다른 키 입력을 기다림
                if all(k in ["CTRL", "SHIFT", "ALT", "GUI"] for k in pressed_keys):
                    print(f"Special keys pressed: {pressed_keys}. Waiting for additional key...")
                    return

                # 키 이름과 KMK 코드 저장
                combined_keys = "+".join(sorted(pressed_keys))  # 조합된 키 이름 생성
                kmk_code = KMK_KEYCODES.get(keyname.split("+")[-1], None)  # 마지막 키만 KMK 코드로 매핑
                if kmk_code:
                    self.layers[self.current_layer][index] = combined_keys  # 조합된 키 이름 저장
                    # keymaps[index] = kmk_code

                    # UI 업데이트
                    self.labels[index].setText(combined_keys)
                    print(f"Key assigned: {combined_keys}")# -> {kmk_code}")
                    return False  # 리스너 종료
            except Exception as e:
                print(f"Error: {e}")
                return False

        def on_release(key):
            # 키 릴리스 시 pressed_keys에서 제거
            if isinstance(key, Key):  # 특수키 처리
                keyname = str(key).replace("Key.", "").upper()
                keyname = SPECIAL_KEYS.get(keyname, keyname)  # 특수키 매핑
            elif hasattr(key, 'char') and key.char:  # 일반 키 처리
                if key.char in ASCII_CONTROL_MAP:  # ASCII 제어 문자 처리
                    keyname = ASCII_CONTROL_MAP[key.char]
                else:
                    keyname = key.char.upper()
            else:
                keyname = str(key).upper()

            if keyname in pressed_keys:
                pressed_keys.remove(keyname)

        # 키 입력 리스너 시작
        with Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

    def on_macro_button_clicked(self, index):
        key, ok = QtWidgets.QInputDialog.getText(None, "Assign Macro", "Seperate steps by comma. No space allowed.\nType ctrl+, alt+, shift+, sl+(Switch Layer Toggle)\nif you want to use the hot key.\n\nEnter macro:")
        if ok and key:
            # 매크로 키 입력 처리
            key= key.upper()
            if len(self.layers[self.current_layer]) <= index:
                self.layers[self.current_layer].extend(["UnAssigned"] * (index - len(self.layers[self.current_layer]) + 1))

            # 데이터 업데이트
            self.layers[self.current_layer][index] = "[MACRO] " + key
            print(f"Updated layer {self.current_layer}: {self.layers[self.current_layer]}")

            # UI 업데이트
            self.labels[index].setText(key)
            print(f"Macro assigned: {key}")

    def on_print_clicked(self):
        """키맵을 KMK 코드로 변환하여 파일에 저장하는 함수"""
        if self.boardPath:
            keypad_file = os.path.join(self.boardPath, "keymaps.json")
            if keypad_file:
                with open(keypad_file, 'w') as f:
                    json.dump(self.layers, f, indent=4)

    def on_set_board_path_clicked(self):
        board_path = QtWidgets.QFileDialog.getExistingDirectory(None, "Select Board Path", "")
        if board_path:
            self.boardPath = board_path
            self.pathLabel.setText(f"Board Path: {board_path}")

    def setFont(self, size):
        font = QtGui.QFont()
        font.setFamily("Malgun Gothic")
        font.setPointSize(size)
        self.centralwidget.setFont(font)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
