import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from pynput.keyboard import Listener, Key, KeyCode

# KMK 키코드 매핑을 수동으로 정의
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

keymaps = [None] * 12  # KMK 코드 저장 배열
keynames = ["UnAssigned"] * 12  # 키 이름 저장 배열

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.gridLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.gridLayoutWidget.setGeometry(QtCore.QRect(40, 20, 571, 422))
        self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.gridLayout = QtWidgets.QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setHorizontalSpacing(0)
        self.gridLayout.setVerticalSpacing(40)
        self.gridLayout.setObjectName("gridLayout")

        # 반복문으로 레이아웃과 위젯 생성
        self.labels = []
        self.buttons = []
        self.create_layout_and_widgets(12, 0)  # 0부터 시작하는 인덱스

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
        self.actionSave_As = QtWidgets.QAction(MainWindow)
        self.actionSave_As.setObjectName("actionSave_As")
        self.actionExit = QtWidgets.QAction(MainWindow)
        self.actionExit.setObjectName("actionExit")
        self.menuFile.addAction(self.actionNew)
        self.menuFile.addAction(self.actionLoad)
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionSave_As)
        self.menuFile.addAction(self.actionExit)
        self.menubar.addAction(self.menuFile.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def create_layout_and_widgets(self, ranges, addVal):
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
            label.setText("UnAssigned")
            layout.addWidget(label)
            self.labels.append(label)

            button = QtWidgets.QPushButton(self.gridLayoutWidget)
            button.setObjectName(f"pushButton_{i + addVal}")
            button.setText("Assign Key")
            layout.addWidget(button)
            self.buttons.append(button)
            button.clicked.connect(lambda _, idx=i + addVal: self.on_button_clicked(idx))  # 버튼 클릭 시 이벤트 연결

            # 그리드 레이아웃에 추가 (4x3 기준)
            row = i // 4  # 3열 기준으로 행 계산
            col = i % 4   # 열 계산
            self.gridLayout.addLayout(layout, row, col, 1, 1)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "KeyMapper"))
        self.menuFile.setTitle(_translate("MainWindow", "File"))
        self.actionNew.setText(_translate("MainWindow", "New"))
        self.actionLoad.setText(_translate("MainWindow", "Load"))
        self.actionSave.setText(_translate("MainWindow", "Save"))
        self.actionSave_As.setText(_translate("MainWindow", "Save As"))
        self.actionExit.setText(_translate("MainWindow", "Exit"))

    def on_button_clicked(self, index):
        print(f"Waiting for key input for button {index}...")

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
                    keynames[index] = combined_keys  # 조합된 키 이름 저장
                    keymaps[index] = kmk_code

                    # UI 업데이트
                    self.labels[index].setText(keynames[index])
                    print(f"Key assigned: {combined_keys} -> {kmk_code}")
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


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
