# DLSSG Manager v1.6.0

同步上游 **DLSSG SM86 0.3.1**（tag `0.3.1`，commit `f275d45`）。

## 上游 0.3.1 带来的变更

1. **恢复 RTX 20 系（Turing / SM75）支持** —— 0.3.0 在部分 RTX 20 上会拒绝启用帧生成，0.3.1 修复。
2. **INI 逐键回退** —— 单个配置键无效时不再整份配置失效，按 `configuration_warning` 逐键回退。
3. **不支持的 backend 开关剔除后继续** —— 不再因未知开关直接失败，按 `kernel_selection_unsupported{stripped_flags}` 剔除后继续。
4. **出厂 `MaxGeneratedFrames` 由 5 改为 3（4X）** —— 本版倍率默认值同步对齐为 4X。
5. **新增 `fg_gate_*` 诊断**（Level=2）—— 便于定位帧生成门控未通过的原因。
6. **12 个代理 DLL 全部重编译重签名** —— version / winmm / dbghelp / dinput8 / dxgi / d3d12 及 310.1 子目录全套。
7. **RTX 30 系数值与性能逐位一致** —— 本次重建不改变 30 系行为。
8. **多代理共存安全** —— 多个代理 DLL 同时存在时不再互相干扰。

## 本版内置运行库

| 运行库 | 位置 | 倍率上限 | 说明 |
|---|---|---|---|
| 310.9 | 根目录 | 6X | 最新，默认 |
| 310.1 | `310.1/` 子目录 | 4X | 老版本，需要时手动选 |

## 兼容性

- 入口分层保持与上游一致：`version.dll`（首选）→ `winmm.dll` → `dbghelp.dll` → `dinput8.dll`；
  `dxgi.dll` / `d3d12.dll` 走渲染路径，与工具类入口互斥，界面已做二选一约束。
- 旧版部署仍可被识别（哈希表保留 0.3.0 全套 + native 表），无需手动清理即可升级。

## 安装

- `DLSSG_Manager_1.6.0_setup_x64.exe` —— 安装版
- `DLSSG_Manager_1.6.0_portable_x64.zip` —— 便携版，解压即用

## 提示

- 显卡伪装改注册表后需重启显卡设备（界面内提供一键按钮）才会被游戏/DXGI 识别。
- 部署前请关闭目标游戏，HAGS 检测与一键开关在「系统准备」区。