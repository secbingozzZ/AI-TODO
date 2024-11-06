# -*- coding: utf-8 -*-
import sys
import os
import json
import configparser
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QCheckBox,
    QLabel, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings, QSharedMemory


class DecomposeThread(QThread):
    # 定义一个信号，当任务分解完成时发出
    finished = pyqtSignal(list)

    def __init__(self, task_text):
        super().__init__()
        self.task_text = task_text

    def run(self):
        # 调用AI接口获取子任务
        subtasks = self._get_ai_subtasks(self.task_text)
        # 发出完成信号，传递子任务列表
        self.finished.emit(subtasks)

    def _get_ai_subtasks(self, task_text):
        # 读取API配置
        config = configparser.ConfigParser()
        config.read('api_config.ini')
        api_key = config['API']['api_key']
        api_url = config['API']['api_url']

        # 构建请求头和请求体
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个任务分解专家，请将任务分解为若干个具体的子任务，并以json列表格式返回结果，json列表中直接是字符串"
                },
                {
                    "role": "user",
                    "content": task_text
                }
            ],
            "stream": False
        }

        try:
            # 发送请求并处理响应
            response = requests.post(f"{api_url}/v1/chat/completions", headers=headers, json=body)
            if response.status_code == 200:
                try:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    content = content.strip().replace("```json", "").replace("```", "")
                    subtasks = json.loads(content)
                    if isinstance(subtasks, list):
                        return subtasks
                except (json.JSONDecodeError, KeyError):
                    pass
                print("API返回的不是有效的JSON列表格式")
            else:
                print(f"API请求失败，状态码: {response.status_code}")
        except requests.exceptions.RequestException as e:
            # 捕获网络异常并弹出错误对话框
            self._show_error_dialog(f"网络请求失败: {str(e)}")
        return []

    def _show_error_dialog(self, message):
        # 显示错误对话框
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("网络错误")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()


class AITodoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tasks = []  # 存储任务的列表
        self.setWindowTitle("AI驱动的Todo")  # 设置窗口标题
        self.setGeometry(100, 100, 600, 400)  # 设置窗口大小
        self._setup_ui()  # 初始化UI
        self.load_window_geometry()  # 加载窗口位置和大小
        self.load_tasks()  # 加载任务
        self.render_tasks()  # 渲染任务列表

    def _setup_ui(self):
        # 设置主窗口的布局和控件
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # 置顶按钮
        self.pin_button = QPushButton("置顶")
        self.pin_button.setCheckable(True)
        self.pin_button.clicked.connect(self.toggle_window_on_top)
        main_layout.addWidget(self.pin_button)

        # 标题标签
        title_label = QLabel("AI驱动的Todo", alignment=Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 输入框和添加按钮
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("添加新项目...")
        self.add_button = QPushButton("添加")
        self.add_button.clicked.connect(self.add_task)
        self.input_field.returnPressed.connect(self.add_task)
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.add_button)
        main_layout.addLayout(input_layout)

        # 任务列表
        self.todo_list = QListWidget()
        main_layout.addWidget(self.todo_list)

    def closeEvent(self, event):
        # 保存任务和窗口状态
        self.save_tasks()
        self.save_window_geometry()
        super().closeEvent(event)

    def save_window_geometry(self):
        # 保存窗口的几何信息
        settings = QSettings("MyCompany", "AITodoApp")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())

    def load_window_geometry(self):
        # 加载窗口的几何信息
        settings = QSettings("MyCompany", "AITodoApp")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        window_state = settings.value("windowState")
        if window_state:
            self.restoreState(window_state)

    def save_tasks(self):
        # 将任务保存到JSON文件
        with open('tasks.json', 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)

    def load_tasks(self):
        # 从JSON文件加载任务
        if os.path.exists('tasks.json'):
            with open('tasks.json', 'r', encoding='utf-8') as f:
                self.tasks = json.load(f)

    def render_tasks(self):
        # 渲染任务列表
        self.todo_list.clear()
        for task in self.tasks:
            self._create_task_item(task)

    def add_task(self):
        # 添加新任务
        task_text = self.input_field.text()
        if task_text:
            new_task = {
                'text': task_text,
                'completed': False,
                'expanded': True,
                'subtasks': []
            }
            self.tasks.append(new_task)
            self._create_task_item(new_task)
            self.input_field.clear()
            self.save_tasks()

    def _create_task_item(self, task, parent_item=None, level=0):
        # 创建任务项并添加到任务列表中
        item = QListWidgetItem()
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(level * 20, 0, 0, 0)

        # 任务复选框
        checkbox = QCheckBox()
        checkbox.setChecked(task['completed'])
        checkbox.stateChanged.connect(lambda state, t=task: self.update_task_state(t, state))
        layout.addWidget(checkbox)

        # 任务标签
        task_label = QLabel(task['text'])
        layout.addWidget(task_label)

        layout.addStretch()

        # 展开/收起按钮（仅当有子任务时显示）
        if 'subtasks' in task and task['subtasks']:  # 检查是否有子任务
            toggle_button = QPushButton("收起" if task['expanded'] else "展开")
            toggle_button.clicked.connect(lambda _, t=task, i=item, b=toggle_button: self.toggle_subtasks(t, i, b))
            
            # 根据任务的展开状态设置按钮的背景颜色
            if task['expanded']:
                toggle_button.setStyleSheet("background-color: lightgreen;")
            else:
                toggle_button.setStyleSheet("background-color: lightcoral;")
            
            layout.addWidget(toggle_button)
        else:
            toggle_button = None
        
        # 分解按钮
        decompose_button = QPushButton("分解")
        decompose_button.clicked.connect(lambda _, t=task, b=decompose_button: self.decompose_task(t, b))
        layout.addWidget(decompose_button)

        # 删除按钮
        delete_button = QPushButton("删除")
        delete_button.clicked.connect(lambda _, t=task, i=item: self.delete_task(t, i))
        layout.addWidget(delete_button)

        item.setSizeHint(widget.sizeHint())
        if parent_item and not parent_item.task_data['expanded']:
            item.setHidden(True)

        item.task_data = task
        self.todo_list.addItem(item)
        self.todo_list.setItemWidget(item, widget)

        # 递归创建子任务项
        for subtask in task.get('subtasks', []):
            self._create_task_item(subtask, parent_item=item, level=level + 1)

    def update_task_state(self, task, state):
        # 更新任务的完成状态
        task['completed'] = (state == Qt.Checked)
        self._update_subtasks_state(task, task['completed'])
        parent_task = self._find_parent_task(task)
        if parent_task:
            self._update_parent_task_state(parent_task)
        self.save_tasks()
        self.render_tasks()

    def _update_subtasks_state(self, task, completed):
        # 更新子任务的完成状态
        for subtask in task.get('subtasks', []):
            subtask['completed'] = completed
            self._update_subtasks_state(subtask, completed)

    def _update_parent_task_state(self, task):
        # 更新父任务的完成状态
        if all(subtask['completed'] for subtask in task.get('subtasks', [])):
            task['completed'] = True
        else:
            task['completed'] = False
        parent_task = self._find_parent_task(task)
        if parent_task:
            self._update_parent_task_state(parent_task)

    def toggle_subtasks(self, task, item, button):
        # 展开或收起子任务
        task['expanded'] = not task['expanded']
        button.setText("收起" if task['expanded'] else "展开")
        
        # 根据任务的展开状态设置按钮的背景颜色
        if task['expanded']:
            button.setStyleSheet("background-color: lightgreen;")
        else:
            button.setStyleSheet("background-color: lightcoral;")
        
        start_index = self.todo_list.row(item) + 1
        self._toggle_subtasks_visibility(task, start_index, task['expanded'])
        self.save_tasks()

    def _toggle_subtasks_visibility(self, task, start_index, visible):
        # 切换子任务的可见性
        end_index = start_index
        for subtask in task.get('subtasks', []):
            item = self.todo_list.item(end_index)
            item.setHidden(not visible)
            if 'subtasks' in subtask:
                end_index = self._toggle_subtasks_visibility(subtask, end_index + 1, visible and subtask['expanded'])
            else:
                end_index += 1
        return end_index

    def delete_task(self, task, item):
        # 删除任务
        self._remove_task_from_list(task, self.tasks)
        self.render_tasks()
        self.save_tasks()

    def _remove_task_from_list(self, target_task, task_list):
        # 从任务列表中移除任务
        for task in task_list:
            if task == target_task:
                task_list.remove(task)
                return True
            if self._remove_task_from_list(target_task, task.get('subtasks', [])):
                return True
        return False

    def decompose_task(self, task, button):
        # 分解任务为子任务
        self.set_task_buttons_enabled(task, False)
        self._set_loading_state(button, True)
        
        # 清空现有的子任务
        task['subtasks'] = []
        
        self.decompose_thread = DecomposeThread(task['text'])
        self.decompose_thread.finished.connect(lambda subtasks, t=task, b=button: self._on_decomposition_finished(t, subtasks, b))
        self.decompose_thread.start()

    def _on_decomposition_finished(self, task, subtasks, button):
        # 任务分解完成后的处理
        self.set_task_buttons_enabled(task, True)
        self._set_loading_state(button, False)
        for text in subtasks:
            new_subtask = {'text': text, 'completed': False, 'expanded': True, 'subtasks': []}
            task.setdefault('subtasks', []).append(new_subtask)
        self.save_tasks()
        self.render_tasks()

    def _set_loading_state(self, button, is_loading):
        # 设置按钮的加载状态
        button.setText("分解中..." if is_loading else "分解")
        button.setEnabled(not is_loading)

    def set_task_buttons_enabled(self, task, enabled):
        # 启用或禁用任务的按钮
        for i in range(self.todo_list.count()):
            item = self.todo_list.item(i)
            if getattr(item, 'task_data', None) == task:
                widget = self.todo_list.itemWidget(item)
                if widget:
                    for btn_name in ['decompose_button', 'delete_button']:
                        btn = widget.findChild(QPushButton, btn_name)
                        if btn:
                            btn.setEnabled(enabled)
                break

    def toggle_window_on_top(self):
        # 切换窗口是否置顶
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.pin_button.isChecked())
        self.show()

    def _find_parent_task(self, target_task, tasks=None, visited=None):
        # 查找父任务
        tasks = tasks or self.tasks
        visited = visited or set()  # 初始化已访问任务的集合

        for task in tasks:
            if id(task) in visited:  # 如果任务已经访问过，跳过
                continue
            visited.add(id(task))  # 将当前任务标记为已访问

            if target_task in task.get('subtasks', []):
                return task
            parent = self._find_parent_task(target_task, task.get('subtasks', []), visited)
            if parent:
                return parent
        return None


if __name__ == "__main__":
    # 创建一个共享内存对象，用于检测是否已有实例在运行
    shared_memory = QSharedMemory("AITodoAppInstance")
    
    # 初始化 QApplication
    app = QApplication(sys.argv)
    
    if not shared_memory.create(1):  # 如果共享内存已存在，说明已有实例在运行
        # 弹出提示框，告知用户窗口已存在
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("提示")
        msg_box.setText("窗口已存在")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
        sys.exit(0)  # 退出程序
    else:
        # 程序入口，启动应用
        window = AITodoApp()
        window.show()
        sys.exit(app.exec_())