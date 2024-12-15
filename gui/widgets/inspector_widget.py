import os

from functools import partial

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QRadioButton,
    QSlider,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from audio.audio_conf import dict_audio_features
#from nodeeditor.utils import dumpException
#from node.node_conf import SHADER_NODES, get_class_from_opcode, LISTBOX_MIMETYPE


class QDMInspector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.uniform_window = None

    def initUI(self):
        grid = QVBoxLayout()
        grid.insertStretch(-1, -1)
        self.grid = grid
        grid.addWidget(QCheckBox())
        self.setLayout(grid)

    def addLayout(self, obj_connect=None):  # TODO: redraw layout at each onSelected -> Node
        for name, properties in obj_connect.items():
            self.grid.addWidget(self.createWidget(properties))

        self.grid.insertStretch(-1, 1)

    def createWidget(self, properties):
        if properties["widget"] == "Slider":
            return self.createSlider(properties)

        if properties["widget"] == "CheckBox":
            return self.createCheckBox(properties)

    def createCheckBox(self, properties):
        name = properties["name"].lower().capitalize()
        name = name.replace("_", " ")
        groupBox = QGroupBox("")

        checkbox = QRadioButton(name)
        checkbox.setChecked(bool(properties["value"]))
        connect = properties["connect"]

        def fine_connect(v):
            connect(int(checkbox.isChecked()))

        checkbox.toggled.connect(fine_connect)

        vbox = QVBoxLayout()
        vbox.addWidget(checkbox)
        vbox.addStretch(1)
        groupBox.setLayout(vbox)
        groupBox.setFlat(True)
        return groupBox

    def createSlider(self, properties):
        name = properties["name"].lower().capitalize()
        name = name.replace("_", " ")
        groupBox = QGroupBox(name)
#       groupBox.setForeground("#FFB500")
        slider = QSlider(Qt.Horizontal)
        slider.setFocusPolicy(Qt.StrongFocus)
        slider.setTickPosition(QSlider.TicksBothSides)
        slider.setTickInterval(10)
        slider.setMinimum(0)
        slider.setMaximum(100)

        value = properties["value"]
        minmax_range = properties["maximum"] - properties["minimum"]
        value = (value - properties["minimum"]) / minmax_range
        slider.setValue(int(value * 100))
        slider.setSingleStep(1)

        connect = properties["connect"]

        def fine_connect(v):
            connect(v / 100.0 * minmax_range + properties["minimum"])

        slider.valueChanged.connect(fine_connect)

        vbox = QVBoxLayout()
        vbox.addWidget(slider)
        vbox.addStretch(1)
        groupBox.setLayout(vbox)
        groupBox.setFlat(True)
        return groupBox

    def createUniformsToolbox(self, uniformsBinding):
        groupBox = QGroupBox("Uniforms Binding")
        uniform_window = self.createUniformWindow(uniformsBinding)

        vbox = QVBoxLayout()
        vbox.addWidget(uniform_window)

        groupBox.setLayout(vbox)

        self.grid.addWidget(groupBox)
        self.grid.insertStretch(-1, -1)

    def createSetWinSizeToolbox(self, obj):
        callback = obj.changeWindowSize
        win_size_ref = obj.win_size

        groupBox = QGroupBox("Resolution")
        vbox = QVBoxLayout()

        def custom_callback(win_size, current_widget, callback):
            current_widget.setText(str(win_size))
            callback(win_size)

        def callback_factory(win_size, current_widget, callback):
            return lambda: custom_callback(win_size, current_widget, callback)

        button_widget = QToolButton()
        button_widget.setText(str(win_size_ref))
        button_widget.setPopupMode(QToolButton.MenuButtonPopup)
        menu = QMenu()
        win_sizes_list = [
            (1920, 1080),
            (1280, 720),
            (960, 540),
            (640, 360),
            (480, 270),
            (320, 180),
            (240, 135),
            (160, 90),
            (80, 45),
            (64, 36),
        ]

        for j, win_size in enumerate(win_sizes_list):
            action = menu.addAction(str(win_size))
            action.triggered.connect(callback_factory(win_size, button_widget, callback))

        button_widget.setMenu(menu)
        vbox.addWidget(button_widget)
        groupBox.setLayout(vbox)
        self.grid.addWidget(groupBox)
        self.grid.insertStretch(-1, -1)

    def createUniformWindow(self, uniformsBinding):
        return UniformWidget(uniformsBinding)

    def createCpuParametersToolbox(self, parameters_informations):
        groupBox = QGroupBox("Cpu Transformation parameters")
        vbox = QVBoxLayout()
        parameter_window = self.createParametersWindow(parameters_informations)
        vbox.addWidget(parameter_window)
        vbox.sizeHint = lambda: QSize(450, 500)
        groupBox.setLayout(vbox)
        self.grid.addWidget(groupBox)
        self.grid.insertStretch(-1, -1)

    def createGpuParametersToolbox(self, parameters_informations):
        groupBox = QGroupBox("Gpu Transformation parameters")
        vbox = QVBoxLayout()
        parameter_window = self.createParametersWindow(parameters_informations)
        vbox.addWidget(parameter_window)
        vbox.sizeHint = lambda: QSize(450, 500)
        groupBox.setLayout(vbox)
        self.grid.addWidget(groupBox)
        self.grid.insertStretch(-1, -1)

    def createParametersWindow(self, parameters_informations):
        return ParametersWidget(parameters_informations)

    def clearLayout(self):
        while self.grid.count():
            child = self.grid.takeAt(0)

            if child.widget():
                child.widget().deleteLater()

    def updateParametersToSelectedItems(self, obj):
        self.clearLayout()

        if self.uniform_window is not None:
            self.uniform_window.deleteLater()

#       gpu_parameters_informations = obj.getGpuAdaptableParameters()
#       cpu_parameters_informations = obj.getCpuAdaptableParameters()
        uniforms_binding = obj.getUniformsBinding()
        self.createSetWinSizeToolbox(obj)
        self.createGpuParametersToolbox(obj.getGpuAdaptableParameters())
        self.createCpuParametersToolbox(obj.getCpuAdaptableParameters())
        self.createUniformsToolbox(uniforms_binding)


class ParametersWidget(QTabWidget):
    def __init__(self, parameters_informations, parent=None):
        super().__init__(parent)
        self.parameters_informations = parameters_informations
        self.n_programs = len(self.parameters_informations)
        self.initUI()

    def initUI(self):

        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(40, 40, 40))

        self.setAutoFillBackground(True)
        self.setPalette(pal)
        self.setGeometry(800, 800, 250 + 50 * self.n_programs, 1000)
        stylesheet = os.path.join(os.path.dirname(__file__), "qss/qlistwidget-styl.qss")
        stylesheet = open(stylesheet, "r").read()

        stylesheet_tab = os.path.join(os.path.dirname(__file__), "qss/qtabwidget-styl.qss")
        stylesheet_tab = open(stylesheet_tab, "r").read()

        self.setStyleSheet(stylesheet + stylesheet_tab)

        self._all_buttons = {}
        self._all_line_edit_widgets = {}

        for program_name in self.parameters_informations:
            self._all_buttons[program_name] = list()
            self._all_line_edit_widgets[program_name] = list()
            displayed_name = program_name.replace("_", " ").capitalize()
            program_widget = self.createWidget(program_name)
            self.addTab(program_widget, displayed_name)

    def createWidget(self, program_name):
        list_widget = QListWidget()
        parameters = self.parameters_informations[program_name]

        for idx, uniform_name in enumerate(parameters.keys()):
            item = QListWidgetItem()

            parameter_widget = QWidget()
            parameter_layout = QHBoxLayout()

            line_edit_widget = self.getLineEdit(
                parameters[uniform_name], program_name, uniform_name
            )
            button_widget = QPushButton(uniform_name)
            self._all_buttons[program_name].append(button_widget)
            self._all_line_edit_widgets[program_name].append(line_edit_widget)

            button_widget.clicked.connect(partial(self.hide_unhide, idx, program_name))

            parameter_layout.addWidget(button_widget)
            parameter_layout.addWidget(line_edit_widget)
            parameter_layout.setSizeConstraint(parameter_layout.SetFixedSize)

            parameter_widget.setLayout(parameter_layout)

            item.setSizeHint(parameter_widget.sizeHint())
            list_widget.addItem(item)
            list_widget.setItemWidget(item, parameter_widget)

        return list_widget

    def hide_unhide(self, widget_index, program_name):
        widget = self._all_line_edit_widgets[program_name][widget_index]

        if widget.isHidden():
            widget.show()
        else:
            widget.hide()

    def getLineEdit(self, parameter, program_name, uniform_name):
        textfield = QLineEdit(self)
        textfield.setText(parameter["eval_function"]["value"])

        callback = parameter["eval_function"]["connect"]

        def custom_callback():
            text = textfield.text()
            callback(text)

        def get_callback():
            return lambda: custom_callback()

        textfield.returnPressed.connect(get_callback())
        textfield.hide()
        return textfield


class UniformWidget(QTabWidget):
    def __init__(self, uniforms_informations, parent=None):
        super().__init__(parent)
        self.uniforms_informations = uniforms_informations
        self.n_programs = len(self.uniforms_informations)
        self.initUI()

    def initUI(self):
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(40, 40, 40))

        self.setAutoFillBackground(True)
        self.setPalette(pal)
        self.setGeometry(800, 800, 250 + 50 * self.n_programs, 1500)
        stylesheet = os.path.join(os.path.dirname(__file__), "qss/qlistwidget-styl.qss")
        stylesheet = open(stylesheet, "r").read()

        stylesheet_tab = os.path.join(
            os.path.dirname(__file__), "qss/qtabwidget-styl.qss"
        )
        stylesheet_tab = open(stylesheet_tab, "r").read()

        self.setStyleSheet(stylesheet + stylesheet_tab)

        for program_name in self.uniforms_informations:
            displayed_name = program_name.replace("_", " ").capitalize() + "Program"
            program_widget = self.createWidget(program_name)
            self.addTab(program_widget, displayed_name)

    def createWidget(self, program_name):
        list_widget = QListWidget()
        uniforms = self.uniforms_informations[program_name]

        for uniform in uniforms:
            item = QListWidgetItem()

            uniform_widget = QWidget()
            uniform_layout = QHBoxLayout()

            text_widget = QLabel("   " + uniform)
            uniform_layout.addWidget(text_widget)

            combo_widget = self.getToolButtonWidget(uniform, program_name)
            uniform_layout.addWidget(combo_widget)

            uniform_widget.setLayout(uniform_layout)

            item.setSizeHint(uniform_widget.sizeHint())
            list_widget.addItem(item)
            list_widget.setItemWidget(item, uniform_widget)

        return list_widget

    def getToolButtonWidget(self, uniform_name, program_name):
        if self.uniforms_informations[program_name][uniform_name]["type"] is None:
            current_param = "default"
        else:
            current_param = self.uniforms_informations.uniforms[program_name][
                uniform_name
            ]["param_name"]

        button_widget = QToolButton()
        button_widget.setText(current_param)
        button_widget.setPopupMode(QToolButton.MenuButtonPopup)

        callback = self.uniforms_informations.callback

        def custom_callback(program_name, uniform_name, feature_name, type, current_widget):
            current_widget.setText(feature_name)
            callback(program_name, uniform_name, feature_name, type)

        def callback_factory(feature_name, type, current_widget):
            return lambda: custom_callback(
                program_name, uniform_name, feature_name, type, current_widget
            )

        menu = QMenu()
        action = menu.addAction(current_param)
        action.triggered.connect(callback_factory("default", None, button_widget))
        audio_features = dict_audio_features

        for i, (audio_feature_type, features_list) in enumerate(audio_features.items()):
            sub_menu = menu.addMenu(audio_feature_type)

            for j, feature in enumerate(features_list):
                action = sub_menu.addAction(feature)
                action.triggered.connect(callback_factory(feature, "audio_features", button_widget))

        button_widget.setMenu(menu)

        return button_widget
