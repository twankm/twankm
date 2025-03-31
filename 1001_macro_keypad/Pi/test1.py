import sys
from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(400, 300)
        self.pushButton00 = QtWidgets.QPushButton(Form)
        self.pushButton00.setGeometry(QtCore.QRect(150, 120, 75, 23))
        self.pushButton00.setObjectName("pushButton")
        self.pushButton01 = QtWidgets.QPushButton(Form)
        self.pushButton01.setGeometry(QtCore.QRect(150, 160, 75, 23))
        self.pushButton01.setObjectName("pushButton01")

        self.retranslateUi(Form)
        # QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Form"))
        self.pushButton00.setText(_translate("Form", "PushButton"))
        self.pushButton01.setText(_translate("Form", "PushButton"))


class MainWindow(QtWidgets.QWidget):  # QWidget을 상속받는 클래스 생성
    def __init__(self):
        super().__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.ui.pushButton00.clicked.connect(self.on_pushButton_clicked)
        self.ui.pushButton01.clicked.connect(self.on_pushButton_clicked)

    def on_pushButton_clicked(self):
        print("Button clicked!")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()  # MainWindow 인스턴스 생성
    win.show()  # 창 표시
    sys.exit(app.exec_())  # 애플리케이션 실행