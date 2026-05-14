# PromptForge

PromptForge 是一个 Windows 桌面客户端，用来分类保存 AI 绘画提示词、管理参考图，并把不同素材组合成完整提示词。

## 功能

- 按分类管理提示词素材
- `Character` 到 `ArtStyle` 是系统分类，不可删除；组合器要求每个系统分类至少选择一条素材
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

```powershell
.\scripts\setup_env.ps1
.\.venv\Scripts\python.exe -m promptforge
```

当前项目使用 pyenv 固定 Python 3.12.10，并使用项目内 `.venv` 作为专用环境。当前 PowerShell 如果没有优先加载 pyenv shim，直接运行 `python` 可能仍显示全局版本；请使用 `.\.venv\Scripts\python.exe` 或先执行 `.\.venv\Scripts\Activate.ps1`。

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
