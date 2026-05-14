from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import shutil
import sys

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .db import PromptForgeDB
from .image_store import ImageStore
from .paths import APP_NAME, ensure_data_dirs


USER_ROLE = Qt.ItemDataRole.UserRole
SYSTEM_ROLE = Qt.ItemDataRole.UserRole + 1
PATH_ROLE = Qt.ItemDataRole.UserRole + 2
SYSTEM_BADGE = " 🔒"


def compact_text(text: str) -> str:
    return " ".join((text or "").split())


def format_weight(value: float) -> str:
    text = f"{value:.2f}"
    return text.rstrip("0").rstrip(".")


def fit_combo_to_contents(combo: QComboBox) -> None:
    max_text_width = 0
    metrics = combo.fontMetrics()
    for index in range(combo.count()):
        max_text_width = max(max_text_width, metrics.horizontalAdvance(combo.itemText(index)))

    popup_width = max(220, max_text_width + 72)
    combo.setMinimumWidth(min(popup_width, 420))
    combo.view().setMinimumWidth(popup_width)


def apply_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QMainWindow, QWidget {
            background: #f6f7f8;
            color: #202326;
            font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            font-size: 10pt;
        }
        QLineEdit, QTextEdit, QComboBox, QDoubleSpinBox, QListWidget,
        QTreeWidget, QTableWidget {
            background: #ffffff;
            border: 1px solid #cfd6dc;
            border-radius: 6px;
            selection-background-color: #216c70;
            selection-color: #ffffff;
        }
        QTextEdit {
            padding: 6px;
        }
        QPushButton {
            background: #ffffff;
            border: 1px solid #b9c4cc;
            border-radius: 6px;
            padding: 7px 10px;
            min-height: 22px;
        }
        QPushButton:hover {
            border-color: #216c70;
            background: #eef7f6;
        }
        QPushButton:pressed {
            background: #dbeeed;
        }
        QPushButton#primaryButton {
            background: #216c70;
            border-color: #216c70;
            color: #ffffff;
        }
        QPushButton#dangerButton:hover {
            border-color: #a83b35;
            background: #fff0ef;
        }
        QLabel#sectionLabel {
            color: #4d5963;
            font-weight: 600;
            padding-top: 4px;
        }
        QHeaderView::section {
            background: #e7ecef;
            color: #2f3941;
            border: 0;
            border-right: 1px solid #cfd6dc;
            padding: 6px;
        }
        QTabWidget::pane {
            border: 0;
        }
        QTabBar::tab {
            background: #e7ecef;
            padding: 8px 18px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #ffffff;
            color: #144f52;
        }
        """
    )


class MainWindow(QMainWindow):
    def __init__(self, db: PromptForgeDB, image_store: ImageStore, data_dir: Path):
        super().__init__()
        self.db = db
        self.image_store = image_store
        self.data_dir = data_dir
        self.current_category_id = None
        self.current_item_id = None
        self.checked_item_ids = set()

        self.setWindowTitle(f"{APP_NAME} - AI 绘画提示词管理器")
        self.resize(1280, 760)
        self.setMinimumSize(980, 620)

        self._build_actions()
        self._build_ui()
        self.refresh_categories()
        self.refresh_items()
        self.refresh_composer_items()

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("文件")

        open_data_action = QAction("打开数据目录", self)
        open_data_action.triggered.connect(self.open_data_dir)
        file_menu.addAction(open_data_action)

        backup_action = QAction("备份数据库", self)
        backup_action.triggered.connect(self.backup_database)
        file_menu.addAction(backup_action)

        cleanup_images_action = QAction("清理未引用素材图", self)
        cleanup_images_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        cleanup_images_action.triggered.connect(self.cleanup_unreferenced_images)
        file_menu.addAction(cleanup_images_action)

        file_menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = self.menuBar().addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _build_ui(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_library_tab(), "素材库")
        tabs.addTab(self._build_composer_tab(), "组合器")
        self.setCentralWidget(tabs)

    def _build_library_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        splitter.addWidget(self._build_category_panel())
        splitter.addWidget(self._build_item_table_panel())
        splitter.addWidget(self._build_editor_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 4)
        splitter.setSizes([210, 430, 560])
        return page

    def _build_category_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel("分类")
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        self.category_list = QListWidget()
        self.category_list.currentItemChanged.connect(self.on_category_selected)
        layout.addWidget(self.category_list, 1)

        button_row = QHBoxLayout()
        add_button = QPushButton("新增")
        add_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        add_button.clicked.connect(self.add_category)
        self.remove_category_button = QPushButton("删除")
        self.remove_category_button.setObjectName("dangerButton")
        self.remove_category_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.remove_category_button.clicked.connect(self.delete_category)
        button_row.addWidget(add_button)
        button_row.addWidget(self.remove_category_button)
        layout.addLayout(button_row)
        return panel

    def _build_item_table_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel("提示词素材")
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索标题、提示词、标签或分类")
        self.search_input.textChanged.connect(self.refresh_items)
        layout.addWidget(self.search_input)

        self.item_table = QTableWidget(0, 5)
        self.item_table.setHorizontalHeaderLabels(["标题", "分类", "标签", "参考图", "更新"])
        self.item_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.item_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.item_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.item_table.verticalHeader().setVisible(False)
        header = self.item_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.item_table.itemSelectionChanged.connect(self.on_table_selection_changed)
        layout.addWidget(self.item_table, 1)
        return panel

    def _build_editor_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel("编辑")
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.category_combo = QComboBox()
        self.category_combo.setMinimumContentsLength(18)
        self.category_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.category_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("例如：赛博朋克城市夜景")
        self.positive_input = QTextEdit()
        self.positive_input.setPlaceholderText("正向提示词，例如：neon city street, rainy night...")
        self.positive_input.setMinimumHeight(120)
        self.negative_input = QTextEdit()
        self.negative_input.setPlaceholderText("负面提示词，例如：low quality, blurry...")
        self.negative_input.setMinimumHeight(80)
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("用逗号分隔，例如：人物, 女性, 写实")
        self.weight_input = QDoubleSpinBox()
        self.weight_input.setRange(0.1, 3.0)
        self.weight_input.setSingleStep(0.05)
        self.weight_input.setDecimals(2)
        self.weight_input.setValue(1.0)
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("备注、模型适配、出图心得")
        self.notes_input.setMinimumHeight(70)

        form.addRow("分类", self.category_combo)
        form.addRow("标题", self.title_input)
        form.addRow("正向", self.positive_input)
        form.addRow("负面", self.negative_input)
        form.addRow("标签", self.tags_input)
        form.addRow("权重", self.weight_input)
        form.addRow("备注", self.notes_input)
        layout.addLayout(form)

        button_grid = QGridLayout()
        self.new_button = QPushButton("新建")
        self.new_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.new_button.clicked.connect(self.new_item)
        self.save_button = QPushButton("保存")
        self.save_button.setObjectName("primaryButton")
        self.save_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.save_button.clicked.connect(self.save_item)
        self.save_as_button = QPushButton("另存为")
        self.save_as_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.save_as_button.clicked.connect(self.save_item_as)
        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.delete_button.clicked.connect(self.delete_item)
        button_grid.addWidget(self.new_button, 0, 0)
        button_grid.addWidget(self.save_button, 0, 1)
        button_grid.addWidget(self.save_as_button, 0, 2)
        button_grid.addWidget(self.delete_button, 0, 3)
        layout.addLayout(button_grid)

        refs_label = QLabel("参考图")
        refs_label.setObjectName("sectionLabel")
        layout.addWidget(refs_label)

        self.image_list = QListWidget()
        self.image_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.image_list.setIconSize(QSize(104, 104))
        self.image_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.image_list.setMovement(QListWidget.Movement.Static)
        self.image_list.setMinimumHeight(145)
        self.image_list.itemDoubleClicked.connect(self.open_image_item)
        layout.addWidget(self.image_list)

        image_buttons = QHBoxLayout()
        add_image_button = QPushButton("添加图片")
        add_image_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        add_image_button.clicked.connect(self.add_images)
        remove_image_button = QPushButton("移除选中")
        remove_image_button.setObjectName("dangerButton")
        remove_image_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        remove_image_button.clicked.connect(self.remove_selected_image)
        image_buttons.addWidget(add_image_button)
        image_buttons.addWidget(remove_image_button)
        layout.addLayout(image_buttons)
        return panel

    def _build_composer_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        label = QLabel("选择素材")
        label.setObjectName("sectionLabel")
        left_layout.addWidget(label)

        self.composer_search_input = QLineEdit()
        self.composer_search_input.setPlaceholderText("搜索后勾选要组合的提示词")
        self.composer_search_input.textChanged.connect(self.refresh_composer_items)
        left_layout.addWidget(self.composer_search_input)

        self.composer_requirement_label = QLabel("")
        self.composer_requirement_label.setWordWrap(True)
        left_layout.addWidget(self.composer_requirement_label)

        self.composer_tree = QTreeWidget()
        self.composer_tree.setHeaderLabels(["素材"])
        self.composer_tree.itemChanged.connect(self.on_composer_item_changed)
        self.composer_tree.currentItemChanged.connect(self.on_composer_tree_current_changed)
        left_layout.addWidget(self.composer_tree, 1)

        browse_refs_label = QLabel("当前素材参考图")
        browse_refs_label.setObjectName("sectionLabel")
        left_layout.addWidget(browse_refs_label)

        self.composer_preview_list = QListWidget()
        self.composer_preview_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.composer_preview_list.setIconSize(QSize(92, 92))
        self.composer_preview_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.composer_preview_list.setMovement(QListWidget.Movement.Static)
        self.composer_preview_list.setMinimumHeight(118)
        self.composer_preview_list.itemDoubleClicked.connect(self.open_image_item)
        left_layout.addWidget(self.composer_preview_list)

        action_row = QHBoxLayout()
        generate_button = QPushButton("生成")
        generate_button.setObjectName("primaryButton")
        generate_button.clicked.connect(self.generate_prompt)
        clear_button = QPushButton("清空选择")
        clear_button.clicked.connect(self.clear_composer_selection)
        action_row.addWidget(generate_button)
        action_row.addWidget(clear_button)
        left_layout.addLayout(action_row)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        output_label = QLabel("完整提示词")
        output_label.setObjectName("sectionLabel")
        right_layout.addWidget(output_label)

        self.output_positive = QTextEdit()
        self.output_positive.setPlaceholderText("组合后的正向提示词会出现在这里")
        self.output_negative = QTextEdit()
        self.output_negative.setPlaceholderText("组合后的负面提示词会出现在这里")
        self.output_positive.setMinimumHeight(170)
        self.output_negative.setMinimumHeight(120)
        right_layout.addWidget(QLabel("正向"))
        right_layout.addWidget(self.output_positive, 2)
        right_layout.addWidget(QLabel("负面"))
        right_layout.addWidget(self.output_negative, 1)

        output_buttons = QHBoxLayout()
        copy_positive_button = QPushButton("复制正向")
        copy_positive_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
        copy_positive_button.clicked.connect(self.copy_positive)
        copy_negative_button = QPushButton("复制负面")
        copy_negative_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
        copy_negative_button.clicked.connect(self.copy_negative)
        save_recipe_button = QPushButton("保存组合")
        save_recipe_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        save_recipe_button.clicked.connect(self.save_recipe)
        output_buttons.addWidget(copy_positive_button)
        output_buttons.addWidget(copy_negative_button)
        output_buttons.addWidget(save_recipe_button)
        right_layout.addLayout(output_buttons)

        refs_label = QLabel("已选参考图")
        refs_label.setObjectName("sectionLabel")
        right_layout.addWidget(refs_label)
        self.composer_image_list = QListWidget()
        self.composer_image_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.composer_image_list.setIconSize(QSize(104, 104))
        self.composer_image_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.composer_image_list.setMovement(QListWidget.Movement.Static)
        self.composer_image_list.setMinimumHeight(150)
        self.composer_image_list.itemDoubleClicked.connect(self.open_image_item)
        right_layout.addWidget(self.composer_image_list)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([430, 700])
        return page

    def refresh_categories(self, select_id=None) -> None:
        categories = self.db.list_categories()
        self.category_list.blockSignals(True)
        self.category_list.clear()

        all_item = QListWidgetItem("全部")
        all_item.setData(USER_ROLE, None)
        all_item.setData(SYSTEM_ROLE, False)
        self.category_list.addItem(all_item)
        for category in categories:
            is_system = bool(category.get("is_system"))
            label = f"{category['name']}{SYSTEM_BADGE}" if is_system else category["name"]
            item = QListWidgetItem(label)
            item.setData(USER_ROLE, category["id"])
            item.setData(SYSTEM_ROLE, is_system)
            self.category_list.addItem(item)

        desired = self.current_category_id if select_id is None else select_id
        for index in range(self.category_list.count()):
            item = self.category_list.item(index)
            if item.data(USER_ROLE) == desired:
                self.category_list.setCurrentItem(item)
                break
        else:
            self.category_list.setCurrentRow(0)
            self.current_category_id = None
        self.category_list.blockSignals(False)

        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        for category in categories:
            label = (
                f"{category['name']}{SYSTEM_BADGE}"
                if category.get("is_system")
                else category["name"]
            )
            self.category_combo.addItem(label, category["id"])
        fit_combo_to_contents(self.category_combo)
        self.category_combo.blockSignals(False)

    def refresh_items(self) -> None:
        query = self.search_input.text() if hasattr(self, "search_input") else ""
        rows = self.db.list_items(self.current_category_id, query)
        self.item_table.blockSignals(True)
        self.item_table.setRowCount(0)
        for row_index, row in enumerate(rows):
            self.item_table.insertRow(row_index)
            title_item = QTableWidgetItem(row["title"])
            title_item.setData(USER_ROLE, row["id"])
            self.item_table.setItem(row_index, 0, title_item)
            category_label = (
                f"{row['category_name']}{SYSTEM_BADGE}"
                if row.get("category_is_system")
                else row["category_name"]
            )
            self.item_table.setItem(row_index, 1, QTableWidgetItem(category_label))
            self.item_table.setItem(row_index, 2, QTableWidgetItem(row["tags"]))
            self.item_table.setItem(row_index, 3, QTableWidgetItem(str(row["image_count"])))
            self.item_table.setItem(row_index, 4, QTableWidgetItem(row["updated_at"]))
        self.item_table.blockSignals(False)

    def refresh_composer_items(self) -> None:
        query = self.composer_search_input.text() if hasattr(self, "composer_search_input") else ""
        categories = self.db.list_categories()
        rows = self.db.list_items(query=query)
        grouped = OrderedDict((category["id"], []) for category in categories)
        for row in rows:
            grouped.setdefault(row["category_id"], []).append(row)

        self.composer_tree.blockSignals(True)
        self.composer_tree.clear()
        system_root = QTreeWidgetItem(["系统分类（每类必选）"])
        system_root.setFlags(Qt.ItemFlag.ItemIsEnabled)
        custom_root = QTreeWidgetItem(["自定义分类"])
        custom_root.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.composer_tree.addTopLevelItem(system_root)
        self.composer_tree.addTopLevelItem(custom_root)

        for is_system, root in ((True, system_root), (False, custom_root)):
            for category in categories:
                if bool(category.get("is_system")) != is_system:
                    continue
                items = grouped.get(category["id"], [])
                if query and not items and not is_system:
                    continue
                selected_count = sum(
                    1 for row in items if row["id"] in self.checked_item_ids
                )
                suffix = f"  ({selected_count}/{len(items)})" if is_system else ""
                category_item = QTreeWidgetItem([f"{category['name']}{suffix}"])
                category_item.setData(0, SYSTEM_ROLE, is_system)
                category_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                root.addChild(category_item)
                for row in items:
                    label = row["title"]
                    if row["tags"]:
                        label = f"{label}  [{row['tags']}]"
                    if row.get("image_count"):
                        label = f"{label}  · {row['image_count']}图"
                    child = QTreeWidgetItem([label])
                    child.setData(0, USER_ROLE, row["id"])
                    child.setData(0, SYSTEM_ROLE, is_system)
                    child.setToolTip(0, compact_text(row["prompt_text"]))
                    child.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    state = (
                        Qt.CheckState.Checked
                        if row["id"] in self.checked_item_ids
                        else Qt.CheckState.Unchecked
                    )
                    child.setCheckState(0, state)
                    category_item.addChild(child)
                category_item.setExpanded(True)
        system_root.setExpanded(True)
        custom_root.setExpanded(True)
        self.composer_tree.blockSignals(False)
        self.update_composer_requirement_label()
        self.update_composer_preview_for_current()
        self.update_composer_references()

    def on_category_selected(self, current: QListWidgetItem) -> None:
        self.current_category_id = current.data(USER_ROLE) if current else None
        is_system = bool(current.data(SYSTEM_ROLE)) if current else False
        if hasattr(self, "remove_category_button"):
            self.remove_category_button.setEnabled(
                self.current_category_id is not None and not is_system
            )
        self.refresh_items()

    def on_table_selection_changed(self) -> None:
        selected = self.item_table.selectedItems()
        if not selected:
            return
        item_id = self.item_table.item(selected[0].row(), 0).data(USER_ROLE)
        self.load_item(item_id)

    def add_category(self) -> None:
        name, ok = QInputDialog.getText(self, "新增分类", "分类名称")
        if not ok:
            return
        try:
            category_id = self.db.add_category(name)
        except Exception as exc:
            QMessageBox.warning(self, "无法新增分类", str(exc))
            return
        self.current_category_id = category_id
        self.refresh_categories(select_id=category_id)
        self.refresh_items()
        self.refresh_composer_items()

    def delete_category(self) -> None:
        item = self.category_list.currentItem()
        if not item or item.data(USER_ROLE) is None:
            QMessageBox.information(self, "删除分类", "请选择一个具体分类。")
            return
        if item.data(SYSTEM_ROLE):
            QMessageBox.information(self, "删除分类", "系统分类不可删除。")
            return
        category_id = item.data(USER_ROLE)
        reply = QMessageBox.question(
            self,
            "删除分类",
            f"确定删除分类“{item.text()}”吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_category(category_id)
        except Exception as exc:
            QMessageBox.warning(self, "无法删除分类", str(exc))
            return
        self.current_category_id = None
        self.refresh_categories(select_id=None)
        self.refresh_items()
        self.refresh_composer_items()

    def new_item(self) -> None:
        self.current_item_id = None
        self.title_input.clear()
        self.positive_input.clear()
        self.negative_input.clear()
        self.tags_input.clear()
        self.weight_input.setValue(1.0)
        self.notes_input.clear()
        self.image_list.clear()

        if self.current_category_id is not None:
            index = self.category_combo.findData(self.current_category_id)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
        self.title_input.setFocus()

    def load_item(self, item_id: int) -> None:
        row = self.db.get_item(item_id)
        if not row:
            return
        self.current_item_id = item_id
        index = self.category_combo.findData(row["category_id"])
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        self.title_input.setText(row["title"])
        self.positive_input.setPlainText(row["prompt_text"])
        self.negative_input.setPlainText(row["negative_prompt"])
        self.tags_input.setText(row["tags"])
        self.weight_input.setValue(float(row["weight"]))
        self.notes_input.setPlainText(row["notes"])
        self.reload_item_images()

    def collect_item_form(self, dialog_title: str):
        if self.category_combo.currentIndex() < 0:
            QMessageBox.warning(self, dialog_title, "请先创建或选择分类。")
            return None
        category_id = self.category_combo.currentData()
        title = self.title_input.text().strip()
        prompt_text = self.positive_input.toPlainText().strip()
        if not title:
            QMessageBox.warning(self, dialog_title, "标题不能为空。")
            return None
        if not prompt_text:
            QMessageBox.warning(self, dialog_title, "正向提示词不能为空。")
            return None
        return {
            "category_id": category_id,
            "title": title,
            "prompt_text": prompt_text,
            "negative_prompt": self.negative_input.toPlainText(),
            "tags": self.tags_input.text(),
            "weight": self.weight_input.value(),
            "notes": self.notes_input.toPlainText(),
        }

    def save_item(self) -> bool:
        data = self.collect_item_form("无法保存")
        if not data:
            return False
        if self.current_item_id is None:
            self.current_item_id = self.db.create_item(**data)
        else:
            self.db.update_item(
                self.current_item_id,
                data["category_id"],
                data["title"],
                data["prompt_text"],
                data["negative_prompt"],
                data["tags"],
                data["weight"],
                data["notes"],
            )
        self.current_category_id = data["category_id"]
        self.refresh_categories(select_id=data["category_id"])
        self.refresh_items()
        self.select_table_row(self.current_item_id)
        self.refresh_composer_items()
        self.statusBar().showMessage("已保存提示词。", 2500)
        return True

    def save_item_as(self) -> bool:
        data = self.collect_item_form("无法另存为")
        if not data:
            return False

        source_item_id = self.current_item_id
        new_item_id = self.db.create_item(**data)
        failed_images = []
        if source_item_id is not None:
            for image in self.db.list_images(source_item_id):
                try:
                    stored_name = self.image_store.duplicate_stored_file(image["stored_path"])
                    self.db.add_image(new_item_id, stored_name, image["original_name"])
                except Exception as exc:
                    failed_images.append(f"{image['original_name']}: {exc}")

        self.current_item_id = new_item_id
        self.current_category_id = data["category_id"]
        self.refresh_categories(select_id=data["category_id"])
        self.refresh_items()
        self.select_table_row(new_item_id)
        self.reload_item_images()
        self.refresh_composer_items()
        self.statusBar().showMessage("已另存为新素材。", 2500)
        if failed_images:
            QMessageBox.warning(
                self,
                "部分参考图未复制",
                "新素材已保存，但以下参考图未能复制：\n" + "\n".join(failed_images),
            )
        return True

    def select_table_row(self, item_id: int) -> None:
        for row in range(self.item_table.rowCount()):
            table_item = self.item_table.item(row, 0)
            if table_item and table_item.data(USER_ROLE) == item_id:
                self.item_table.selectRow(row)
                break

    def delete_item(self) -> None:
        if self.current_item_id is None:
            QMessageBox.information(self, "删除提示词", "请先选择要删除的提示词。")
            return
        reply = QMessageBox.question(
            self,
            "删除提示词",
            "确定删除当前提示词和它的参考图记录吗？图片文件也会从本地图片目录移除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        images = self.db.list_images(self.current_item_id)
        for image in images:
            self.image_store.remove(image["stored_path"])
        self.db.delete_item(self.current_item_id)
        self.checked_item_ids.discard(self.current_item_id)
        self.new_item()
        self.refresh_items()
        self.refresh_composer_items()

    def add_images(self) -> None:
        if self.current_item_id is None:
            if not self.save_item():
                return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择参考图",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if not paths:
            return
        failed = []
        for path in paths:
            try:
                stored_name, original_name = self.image_store.copy_into_store(path)
                self.db.add_image(self.current_item_id, stored_name, original_name)
            except Exception as exc:
                failed.append(f"{Path(path).name}: {exc}")
        self.reload_item_images()
        self.refresh_items()
        self.refresh_composer_items()
        if failed:
            QMessageBox.warning(self, "部分图片未导入", "\n".join(failed))

    def reload_item_images(self) -> None:
        self.image_list.clear()
        if self.current_item_id is None:
            return
        for image in self.db.list_images(self.current_item_id):
            self.image_list.addItem(self.make_image_list_item(image))

    def remove_selected_image(self) -> None:
        selected = self.image_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "移除图片", "请先选择一张参考图。")
            return
        list_item = selected[0]
        image_id = list_item.data(USER_ROLE)
        image = self.db.delete_image(image_id)
        if image:
            self.image_store.remove(image["stored_path"])
        self.reload_item_images()
        self.refresh_items()
        self.refresh_composer_items()

    def make_image_list_item(self, image: dict) -> QListWidgetItem:
        path = self.image_store.path_for(image["stored_path"])
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            display_name = f"{image['original_name']} (文件缺失)"
        else:
            icon = QIcon(
                pixmap.scaled(
                    104,
                    104,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            display_name = image["original_name"]
        item = QListWidgetItem(icon, display_name)
        item.setData(USER_ROLE, image["id"])
        item.setData(PATH_ROLE, str(path))
        item.setToolTip(str(path))
        return item

    def open_image_item(self, item: QListWidgetItem) -> None:
        path = item.data(PATH_ROLE) if item else None
        if not path:
            return
        if not Path(path).exists():
            QMessageBox.warning(self, "参考图不存在", f"找不到图片文件：\n{path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def on_composer_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        item_id = item.data(0, USER_ROLE)
        if item_id is None:
            return
        if item.checkState(0) == Qt.CheckState.Checked:
            self.checked_item_ids.add(item_id)
        else:
            self.checked_item_ids.discard(item_id)
        self.update_composer_requirement_label()
        self.update_composer_references()
        self.update_composer_preview_for_current()

    def on_composer_tree_current_changed(
        self, current: QTreeWidgetItem, previous: QTreeWidgetItem
    ) -> None:
        self.update_composer_preview_for_current(current)

    def collect_prompt_ids_from_tree_item(self, item: QTreeWidgetItem) -> list:
        if item is None:
            return []
        item_id = item.data(0, USER_ROLE)
        if item_id is not None:
            return [item_id]
        ids = []
        for index in range(item.childCount()):
            ids.extend(self.collect_prompt_ids_from_tree_item(item.child(index)))
        return ids

    def update_composer_preview_for_current(self, item: QTreeWidgetItem = None) -> None:
        if not hasattr(self, "composer_preview_list"):
            return
        self.composer_preview_list.clear()
        current = item or self.composer_tree.currentItem()
        for item_id in self.collect_prompt_ids_from_tree_item(current):
            for image in self.db.list_images(item_id):
                self.composer_preview_list.addItem(self.make_image_list_item(image))

    def missing_required_system_categories(self) -> list:
        selected_categories = {
            row["category_name"]
            for row in self.selected_prompt_rows()
            if row.get("category_is_system")
        }
        return [
            category["name"]
            for category in self.db.list_categories()
            if category.get("is_system") and category["name"] not in selected_categories
        ]

    def update_composer_requirement_label(self) -> None:
        if not hasattr(self, "composer_requirement_label"):
            return
        missing = self.missing_required_system_categories()
        if missing:
            self.composer_requirement_label.setText(
                "系统分类必选：还缺 " + "、".join(missing)
            )
            self.composer_requirement_label.setStyleSheet("color: #9a5b00;")
        else:
            self.composer_requirement_label.setText("系统分类已满足，可以生成。")
            self.composer_requirement_label.setStyleSheet("color: #216c70;")

    def clear_composer_selection(self) -> None:
        self.checked_item_ids.clear()
        self.output_positive.clear()
        self.output_negative.clear()
        self.refresh_composer_items()

    def selected_prompt_rows(self) -> List[dict]:
        selected = set(self.checked_item_ids)
        return [row for row in self.db.list_items() if row["id"] in selected]

    def generate_prompt(self) -> None:
        rows = self.selected_prompt_rows()
        missing = self.missing_required_system_categories()
        if missing:
            QMessageBox.warning(
                self,
                "系统分类未选完整",
                "系统分类下每个分类至少要选择一条素材。\n\n还缺："
                + "、".join(missing),
            )
            return
        if not rows:
            QMessageBox.information(self, "生成提示词", "请先勾选至少一个提示词素材。")
            return

        positive_parts = []
        seen_positive = set()
        negative_parts = []
        seen_negative = set()

        for row in rows:
            text = compact_text(row["prompt_text"])
            if text and text.lower() not in seen_positive:
                seen_positive.add(text.lower())
                if abs(float(row["weight"]) - 1.0) > 0.001:
                    text = f"({text}:{format_weight(float(row['weight']))})"
                positive_parts.append(text)

            negative = compact_text(row["negative_prompt"])
            if negative and negative.lower() not in seen_negative:
                seen_negative.add(negative.lower())
                negative_parts.append(negative)

        self.output_positive.setPlainText(", ".join(positive_parts))
        self.output_negative.setPlainText(", ".join(negative_parts))
        self.update_composer_references()
        self.statusBar().showMessage("已生成完整提示词。", 2500)

    def update_composer_references(self) -> None:
        if not hasattr(self, "composer_image_list"):
            return
        self.composer_image_list.clear()
        for row in self.selected_prompt_rows():
            for image in self.db.list_images(row["id"]):
                self.composer_image_list.addItem(self.make_image_list_item(image))

    def copy_positive(self) -> None:
        QApplication.clipboard().setText(self.output_positive.toPlainText())
        self.statusBar().showMessage("正向提示词已复制。", 2500)

    def copy_negative(self) -> None:
        QApplication.clipboard().setText(self.output_negative.toPlainText())
        self.statusBar().showMessage("负面提示词已复制。", 2500)

    def save_recipe(self) -> None:
        if not self.output_positive.toPlainText().strip() and self.checked_item_ids:
            self.generate_prompt()
        if not self.output_positive.toPlainText().strip():
            QMessageBox.information(self, "保存组合", "没有可保存的组合内容。")
            return
        title, ok = QInputDialog.getText(
            self,
            "保存组合",
            "组合名称",
            text=datetime.now().strftime("组合 %Y-%m-%d %H%M"),
        )
        if not ok or not title.strip():
            return
        self.db.save_recipe(
            title,
            self.output_positive.toPlainText(),
            self.output_negative.toPlainText(),
            sorted(self.checked_item_ids),
        )
        self.statusBar().showMessage("组合已保存到数据库。", 2500)

    def open_data_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.data_dir)))

    def backup_database(self) -> None:
        target = self.data_dir / "backups" / f"promptforge-{datetime.now():%Y%m%d-%H%M%S}.db"
        shutil.copy2(str(self.db.db_path), str(target))
        QMessageBox.information(self, "备份完成", f"数据库已备份到：\n{target}")

    def cleanup_unreferenced_images(self) -> None:
        referenced_paths = self.db.list_referenced_image_paths()
        unused_files = self.image_store.list_unreferenced_files(referenced_paths)
        if not unused_files:
            QMessageBox.information(self, "清理未引用素材图", "没有发现未引用的素材图。")
            return

        total_size = sum(path.stat().st_size for path in unused_files if path.exists())
        size_mb = total_size / (1024 * 1024)
        preview = "\n".join(path.name for path in unused_files[:8])
        if len(unused_files) > 8:
            preview += f"\n...以及另外 {len(unused_files) - 8} 个文件"
        reply = QMessageBox.question(
            self,
            "清理未引用素材图",
            f"发现 {len(unused_files)} 个未被任何素材引用的图片文件，约 {size_mb:.2f} MB。\n\n"
            f"{preview}\n\n确定删除这些文件吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        removed = 0
        failed = []
        for path in unused_files:
            try:
                path.unlink()
                removed += 1
            except Exception as exc:
                failed.append(f"{path.name}: {exc}")

        self.reload_item_images()
        self.update_composer_preview_for_current()
        self.update_composer_references()
        self.refresh_items()
        if failed:
            QMessageBox.warning(
                self,
                "部分素材图未清理",
                f"已删除 {removed} 个文件，以下文件删除失败：\n" + "\n".join(failed),
            )
        else:
            QMessageBox.information(
                self,
                "清理完成",
                f"已删除 {removed} 个未引用素材图。",
            )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 PromptForge",
            f"{APP_NAME} {__version__}\n\n"
            "用于分类保存 AI 绘画提示词、参考图，并按素材重新组合完整提示词。",
        )


def run() -> None:
    data_dir = ensure_data_dirs()
    db = PromptForgeDB(data_dir / "promptforge.db")
    db.initialize()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_style(app)

    window = MainWindow(db, ImageStore(data_dir / "images"), data_dir)
    window.show()
    sys.exit(app.exec())
