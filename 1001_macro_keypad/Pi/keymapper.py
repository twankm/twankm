from PyQt5 import QtCore, QtGui, QtWidgets

class KC:
    NO = 0
    ESC = 1
    F1 = 2
    F2 = 3

    F3 = 4
    
class Ui_MainWindow(object):

    keymaps = []
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(936, 640)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # 메인 그리드 레이아웃
        self.gridLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.gridLayoutWidget.setGeometry(QtCore.QRect(60, 20, 551, 371))
        self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.gridLayout = QtWidgets.QGridLayout(self.gridLayoutWidget)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setSpacing(10)

        # 반복문으로 레이블과 버튼 생성
        self.groups = []  # 레이블과 버튼을 그룹으로 저장
        for i in range(12):  # 12개의 레이블과 버튼 생성
            layout = QtWidgets.QVBoxLayout()

            label = QtWidgets.QLabel(self.gridLayoutWidget)
            font = QtGui.QFont()
            font.setFamily("맑은 고딕")
            font.setPointSize(12)
            label.setFont(font)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setText(f"UnAssigned {i}")
            layout.addWidget(label)

            button = QtWidgets.QPushButton(self.gridLayoutWidget)
            button.setText(f"Assign {i}")
            layout.addWidget(button)
            self.keymaps.append("")  # 초기화

            # 버튼 클릭 시 동일 그룹의 레이블 내용 변경
            button.clicked.connect(lambda _, lbl=label, idx = i: self.on_button_pressed(lbl, idx))

            # 그룹 저장
            self.groups.append((label, button))

            # 그리드 레이아웃에 추가 (4열 기준)
            row = i // 4
            col = i % 4
            self.gridLayout.addLayout(layout, row, col)

        # 우측 하단 버튼 그룹
        self.horizontalLayoutWidget = QtWidgets.QWidget(self.centralwidget)
        self.horizontalLayoutWidget.setGeometry(QtCore.QRect(630, 470, 271, 121))
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setSpacing(10)

        for i in range(2):  # 두 개의 버튼 그룹 생성
            layout = QtWidgets.QVBoxLayout()

            label = QtWidgets.QLabel(self.horizontalLayoutWidget)
            font = QtGui.QFont()
            font.setFamily("맑은 고딕")
            font.setPointSize(12)
            label.setFont(font)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setText(f"UnAssigned {12 + i}")
            layout.addWidget(label)

            button = QtWidgets.QPushButton(self.horizontalLayoutWidget)
            button.setText(f"Assign {12 + i}")
            layout.addWidget(button)

            # 버튼 클릭 시 동일 그룹의 레이블 내용 변경
            button.clicked.connect(lambda _, lbl=label, idx = 12 + i: self.on_button_pressed(lbl, idx))

            self.horizontalLayout.addLayout(layout)

        # 추가 위젯 (예: Layer 관련 위젯)
        self.labelLayer = QtWidgets.QLabel(self.centralwidget)
        self.labelLayer.setGeometry(QtCore.QRect(760, 20, 111, 31))
        font = QtGui.QFont()
        font.setFamily("Malgun Gothic")
        font.setPointSize(13)
        self.labelLayer.setFont(font)
        self.labelLayer.setText("Layer Number")

        self.labelLayerIdx = QtWidgets.QLabel(self.centralwidget)
        self.labelLayerIdx.setGeometry(QtCore.QRect(840, 50, 56, 31))
        font.setPointSize(20)
        font.setBold(True)
        self.labelLayerIdx.setFont(font)
        self.labelLayerIdx.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
        self.labelLayerIdx.setText("0")

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 936, 21))
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setTitle("File")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        pass

    def on_button_pressed(self, label, index):
        # 버튼 클릭 시 키 입력 대화 상자 표시
        key, ok = QtWidgets.QInputDialog.getText(
            None, "Key Input", "Press a key:"
        )
        if ok and key:  # 사용자가 키를 입력하고 확인을 누른 경우
            label.setText(key)  # 레이블에 입력된 키 표시
            print(index)
            self.keymaps[index] = key
            print(self.keymaps)
            



if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
