# 科研软件支持清单

版本 0.4.0；29 个入口：20 个原生、1 个本地 API、8 个文件交换。商业许可、依赖和可用路径按本机发现与真实任务核实。

| 软件 | 类型 | 操作 | 验收范围 |
|---|---|---|---|
| R | native | script, analysis | 已对声明的本机任务验收 |
| Scientific Python | native | script, analysis | 已对声明的本机任务验收 |
| jamovi (jmv backend) | native | script, analysis | 已对声明的本机任务验收 |
| IBM SPSS Statistics | native | probe, script, analysis | 已对声明的本机任务验收 |
| Stata | native | script, analysis | 接口已编写，待安装/授权及原生验收 |
| SAS | native | script, analysis | 接口已编写，待安装/授权及原生验收 |
| MATLAB | native | script, analysis, chain_dynamics | 已对声明的本机任务验收 |
| GNU Octave | native | script, analysis | 已对声明的本机任务验收 |
| Julia | native | script, analysis | 已对声明的本机任务验收 |
| Jupyter | native | execute | 已对声明的本机任务验收 |
| Pandoc | native | convert | 已对声明的本机任务验收 |
| Quarto | native | render | 已对声明的本机任务验收 |
| XeLaTeX / MiKTeX | native | render | 已对声明的本机任务验收 |
| LibreOffice | native | convert | 已对声明的本机任务验收 |
| Microsoft Word / Excel / PowerPoint | native | convert, recalculate | 已对声明的本机任务验收 |
| Inkscape | native | export | 已对声明的本机任务验收 |
| Graphviz | native | render | 已对声明的本机任务验收 |
| ImageJ | native | macro | 已对声明的本机任务验收 |
| Zotero local API | local_api | search, item, children | 已对声明的本机任务验收 |
| JabRef / BibTeX | file_interchange | bibliography | 文件交换，未证明 GUI 执行 |
| EndNote / RIS | file_interchange | bibliography | 文件交换，未证明 GUI 执行 |
| NVivo / REFI-QDA | file_interchange | codebook, import_codebook | 文件交换，未证明 GUI 执行 |
| MAXQDA / REFI-QDA | file_interchange | codebook, import_codebook | 文件交换，未证明 GUI 执行 |
| ATLAS.ti / REFI-QDA | file_interchange | codebook, import_codebook | 文件交换，未证明 GUI 执行 |
| Origin | native | script | 接口已编写，待安装/授权及原生验收 |
| GraphPad Prism | file_interchange | table | 文件交换，未证明 GUI 执行 |
| JASP | file_interchange | table | 文件交换，未证明 GUI 执行 |
| RStudio | file_interchange | project | 文件交换，未证明 GUI 执行 |
| Git | native | snapshot | 已对声明的本机任务验收 |

Word / Excel / PowerPoint 合并为一个 Office 入口。jamovi 使用独立 R 的 jmv 后端。MATLAB 新增协同 MCP 路线提供交互式代码执行、静态分析和单元测试；Simulink 扩展需另装官方工具包和许可，未注册或未验收时不算已支持。Zotero 协同插件补充合集、全文、笔记和附件工具；写操作服从用户授权。

现有任务的细节见 [jobs.md](jobs.md)；协同插件安装与验收见 [integrations.md](integrations.md)。
