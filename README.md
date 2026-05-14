# PromptForge

PromptForge 是一个 Windows 桌面客户端，用来分类保存 AI 绘画提示词、管理参考图，并把不同素材组合成完整提示词。

## 功能

- 按分类管理提示词素材
- `Character` 到 `ArtStyle` 是系统分类，其中 `FacialFeatures` 与 `Expression` 分别管理五官和表情；组合器要求每个系统分类至少选择一条素材
- 每条素材包含正向提示词、负面提示词、标签、权重和备注
- 每条素材可以导入多张参考图
- 可将当前编辑内容另存为新素材，并复制原素材参考图
- 图片会复制到本地图片目录，SQLite 只保存索引
- 可一键清理图片目录中未被任何素材引用的图片文件
- 在组合器中勾选素材，一键生成完整正向/负面提示词
- 组合器浏览素材时会显示当前素材参考图，双击图片可用系统默认程序打开
- 支持复制结果、保存组合、备份数据库

## 数据位置

- 源码运行：`data/promptforge.db` 与 `data/images/`
- exe 运行：`PromptForge.exe` 旁边的 `PromptForgeData/promptforge.db` 与 `PromptForgeData/images/`

## 开发运行

项目需要 Python 3.12。`.python-version` 用于 pyenv/pyenv-win 用户；没有安装 pyenv 也可以使用系统 Python 3.12 或 Windows Python Launcher。

`setup_env.ps1` 会按顺序尝试：

1. `pyenv exec python`
2. `py -3.12`
3. `python`

找到 Python 3.12.x 后，会创建项目内 `.venv` 作为开发环境。

```powershell
.\scripts\setup_env.ps1
.\.venv\Scripts\python.exe -m promptforge
```

也可以先激活虚拟环境再运行：

```powershell
.\.venv\Scripts\Activate.ps1
python -m promptforge
```

运行数据会写入本地目录，已通过 `.gitignore` 排除。

## 生成 exe

```powershell
.\scripts\build_exe.ps1
```

生成位置：

```text
dist\PromptForge\PromptForge.exe
```

运行 exe 后，数据库和图片会保存在：

```text
dist\PromptForge\PromptForgeData\
```
