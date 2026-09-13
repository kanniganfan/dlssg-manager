<div align="center">

# DLSSG Manager

**为 RTX 20 / 30 系显卡解锁 DLSS 帧生成的一键式图形工具**

简体中文 · 繁體中文 · English

[![Release](https://img.shields.io/badge/Release-v1.1.0-5B8CFF)](#-下载与安装)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-333D52)](#-下载与安装)
[![Upstream](https://img.shields.io/badge/Upstream-dlssg__for__sm86-9B7BFF)](#-致谢与出处)

</div>

---

## 致谢与出处

> **本项目的核心能力完全来自上游项目 [dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86)，由 [sdli1995](https://github.com/sdli1995) 开发维护。**
>
> 正是上游作者对 DLSSG Native（`version.dll` 代理 + SM86 / SM75 内核路由）的逆向与封装，
> 才让 RTX 20 / 30 系用户用上 DLSS Frame Generation。本工具只是站在这个肩膀上，
> 把「找游戏目录、挑入口 DLL、写配置、管备份」这些繁琐步骤做成了图形界面。
>
> **向原作者致以敬意与感谢。** 上游二进制（payload/ 下的 DLL）随本工具原样分发，
> 未做任何修改，版权归原作者所有；如上游项目对你有帮助，请先去给上游一个 Star。

DLSS 与 DLSS Frame Generation 是 NVIDIA Corporation 的商标与专有技术，
运行时依赖用户已安装的 NVIDIA 驱动组件；本仓库不包含、不修改、不分发任何 NVIDIA 专有二进制。

### 为什么做这个工具

和我一起打游戏的好友里，好几个还在用 RTX 30 系、20 系显卡。他们看到别人开帧生成，
抱怨自己的卡"没有生成"。我把原作者的项目分享给他们，结果一个个对着命令行界面挠头
——不会用。于是我把以前的老电脑翻出来，做了这个图形工具：现在他们点两下按钮，
帧生成就开起来了。

这个工具是写给他们的，也写给每一个被命令行劝退的你。

---

## 这是什么

DLSSG Manager 自动扫描本机已安装的 D3D12 游戏，定位真正的渲染 EXE，
一键部署 / 一键恢复上游 DLSSG 代理与配置，让 RTX 20（SM75）/ RTX 30（SM86）
显卡在支持 DLSS 的游戏中开启**帧生成**。

<div align="center">
<img src="docs/screenshot.png" width="720" alt="DLSSG Manager 界面预览">
</div>

### 特性一览

- **自动识别游戏**：Steam / Epic / GOG / Ubisoft 平台库 + 按盘符深度扫描 + 手动添加目录，
  自动穿透启动器定位真正渲染 EXE，并识别 Unreal / Unity 引擎
- **一键启用 / 一键恢复**：入口 DLL 自动避让（version → winmm → dinput8 → winhttp → dxgi），
  绝不覆盖他人物件；部署带 SHA256 校验与自动备份，恢复还原如初
- **分辨率感知**：读取 UE / Unity 配置估算当前分辨率，给出显存增量预算（2X/3X/4X）
- **反作弊提示**：检测到反作弊系统时仅作提示，不影响任何功能使用
- **系统准备**：硬件加速 GPU 计划（HAGS）检测 + 一键开关 + 跳转系统设置，帧时间更稳
- **多语言**：简体中文 / 繁體中文 / English，跟随系统自动选择；
  社区可在 `lang/` 目录添加语言文件，无需重新打包
- **精致界面**：无边框圆角暗色 UI、KANNI 载入动画、macOS 风格三色窗口按钮、像素级文本省略

---

## 下载与安装

前往 [**Releases**](../../releases) 页面下载对应版本（当前 **v1.1.0**）：

| 版本 | 文件 | 适合人群 |
|---|---|---|
| **免安装便携版** | `DLSSG_Manager_1.1.0_portable_x64.zip` | 想即解压即用、绿色不写注册表 |
| **标准安装版** | `DLSSG_Manager_1.1.0_setup_x64.exe` | 想要安装向导、开始菜单/桌面快捷方式与完整卸载 |

**便携版**：解压到任意目录，双击 `DLSSG Manager.exe` 即可。
**安装版**：双击 setup，按向导选择目录安装；卸载请到「设置 → 应用 → 安装的应用」或
开始菜单里的 Uninstall，会一并清理快捷方式与注册表条目。

> 两个版本功能完全一致，都自带 `payload/` 运行库与多语言文件，**不需要安装
> Python / CUDA / 任何运行库**（2–4 秒首次解压启动属正常现象）。

---

## 使用说明

1. 启动后软件自动扫描本机游戏（也可点「深度扫描」按盘符全盘反查，或「手动添加游戏目录…」）；
2. 左侧选中游戏，右侧确认识别结果（渲染进程、分辨率、反作弊提示、部署状态）；
3. 点击 **「一键启用插帧」**，完全退出游戏后重新启动；
4. 在游戏画面设置里打开 **DLSS 帧生成** 并选择 2X / 3X / 4X；
5. 想还原时回到本工具点 **「一键恢复」**，游戏目录会清理干净。

更多细节（显存预算、INI 参数、排查方法、能力边界）见 [docs/使用说明.txt](docs/使用说明.txt)。

### 系统要求

| 项目 | 要求 |
|---|---|
| 系统 | Windows 10 2004+（build 19041）/ Windows 11，x64 |
| 显卡 | NVIDIA RTX 20 系（SM75）/ RTX 30 系（SM86）；RTX 40+ 原生支持无需本工具 |
| 驱动 | 提供 NGX/NVAPI 接口的 NVIDIA 驱动即可 |
| 游戏 | D3D12 且内置 DLSS 运行库（工具会自动判断并提示） |

---

## 多语言

界面语言在**标题栏右上角下拉框**切换（重启程序生效），首次启动跟随系统语言。
新增语言：在程序目录新建 `lang/<语言代码>.json`（UTF-8，键为简体中文原文，值为译文，
另加 `"_meta": {"name": "语言原生名"}`），参照自带 `lang/en_US.json`，重启即可。
命令行也可用 `--lang en_US` 临时指定。

---

## 从源码构建

```bat
git clone https://github.com/kanniganfan/dlssg-manager.git
cd dlssg-manager
scripts\build_windows.bat
```

脚本会自动创建隔离 venv、安装 PySide6 + PyInstaller、打包单文件 exe 到 `dist\`。
运行需要把上游项目的 `payload/` 文件夹（version.dll + altnative/）放在 exe 同级目录；
发布物已在 Release 附件中包含，无需自行寻找。

目录结构：

```
src/       Python 源码（core 逻辑内核 / ui 界面 / i18n 引擎 / main 入口）
lang/      界面语言文件（JSON，可直接编辑或新增语言）
assets/    图标资源
docs/      使用说明与截图
scripts/   构建与维护脚本
```

---

## 能力边界与免责声明

- 仅支持 **Windows x64 + D3D12** 游戏；Vulkan 暂不支持
- 生成帧上限 3 帧（4X 请求）；不支持 6X / 动态倍率 / Reflex Warp
- 上游实卡验证为 RTX 3080 Ti；RTX 20 系（物理 Turing）仍待上游进一步验证
- **反作弊提示**：检测到反作弊系统时仅作提醒；请自觉只在单机 / 离线 / 实验室环境使用，
  线上模式的使用由用户自行判断与承担
- 本工具不联网、不上传任何数据，全部操作在本机完成
- 修改游戏目录前请确认已了解上述内容，使用本工具产生的一切后果由使用者自行承担

---

## 联系方式

- 邮箱：[673100060@qq.com](mailto:673100060@qq.com)（GitHub 账号绑定邮箱）
- 邮箱：[cylqm@qq.com](mailto:cylqm@qq.com)
- 邮箱：[cao673100060@gmail.com](mailto:cao673100060@gmail.com)

欢迎issue / PR；语言文件捐赠（任何语种）尤其欢迎。

---

## License

本项目代码以 [MIT License](LICENSE) 发布。
payload/ 内的 DLSSG 运行库归上游 [dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86)
原作者所有；DLSS 相关技术与商标归 NVIDIA Corporation 所有。

---

<div align="center">

**Again, all credits to [sdli1995/dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86) **

</div>
