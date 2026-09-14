# AutoTLE

使用Vibe Coding

自动化更新业余卫星星历，兼容传统 TLE，并支持 TLE 编号耗尽后的 OMM 多格式输出。

## 功能

- 从 CelesTrak 获取 GP/OMM：默认顺序 `JSON -> KVN -> CSV -> XML -> TLE`。
- CelesTrak 无数据时回退 SatNOGS：`GET /api/tle/?format=json&norad_cat_id=...`，也支持 `sat_id`。
- CelesTrak 与 SatNOGS 都失败时，优先级回退 `localTLE.txt`、`localJSON.json`、已有 `satellites.pkl`。
- 星历统一保存为 OMM 字典列表，pickle 文件为 `./satellites.pkl`。
- 按卫星 `EPOCH` 判断新旧，只有新数据才替换已有星历。
- 每个 `./satellitelists/*.json` 生成同名输出到 `./satellites/`。
- 每个列表更新后都会额外生成同名 TLE `.txt` 到项目根目录 `./`，即使列表未声明 TLE。
- 每次运行覆盖写入 `./logs.txt`，记录每个卫星的编号、名称、来源和更新状态。

## 输出格式

列表文件中的 `formats` 支持：

`TLE`、`3LE`、`2LE`、`JSON`、`JSON-PRETTY`、`KVN`、`CSV`、`XML`

文件映射：

| 格式 | 输出后缀 |
|---|---|
| `TLE` / `3LE` | `.txt` |
| `2LE` | `.2le.txt` |
| `JSON` / `JSON-PRETTY` | `.json` |
| `KVN` | `.kvn` |
| `CSV` | `.csv` |
| `XML` | `.xml` |

## 卫星列表格式

推荐格式：

```json
{
  "formats": ["TLE", "JSON", "KVN", "CSV", "XML"],
  "satellites": [
    {"id": "25544", "name": "ISS(ZARYA)", "query": "CATNR"},
    {"id": "100469", "name": "FUTURE-1", "query": "CATNR"}
  ]
}
```

兼容旧格式：

```json
[
  ["25544", "ISS(ZARYA)", "CATNR"],
  ["100469", "FUTURE-1", "CATNR", ["TLE", "JSON"]]
]
```

`query` 支持 `CATNR`、`NAME`、`INTDES`、`GROUP`、`SPECIAL`、`SATID`、`SAT_ID`。旧列表未声明格式时默认只输出 `TLE`，以保证原行为不变。

## 多列表

`./satellitelists/` 下可放任意数量 JSON 文件。每个文件独立生成：

- `./satellites/<列表名>.<格式后缀>`
- `./<列表名>.txt`，作为根目录 TLE 兼容文件

例如 `AutoTLE.json` 会生成 `./AutoTLE.txt`，不会再由其他列表额外写同名旧文件。

同一次运行中，同一颗卫星只会抓取一次。后续列表会复用本次运行已经获取到的记录，不再重复访问 CelesTrak、SatNOGS 或本地文件源。

## 本地星历源

- `./localTLE.txt`：本地 TLE/3LE/2LE 文本。
- `./localJSON.json`：本地 OMM JSON。
- 回退优先级：`localtle` 高于 `localjson`。localTLE 有匹配记录时不再尝试 localJSON。
- 完整来源顺序：`celestrak > satnogs > localtle > localjson`。

## 日志与状态

默认运行时，控制台会按卫星逐条打印查询和结果；使用 `--quiet` 时只打印最终汇总。

每次执行 `python main.py` 都会覆盖写入：

- `./logs.txt`：本次运行日志。包含运行时间，以及每个卫星的卫星编号、名称、获取来源、更新状态。
- `./satellites_state.md`：Markdown 缓存状态表，按 `satellites.pkl` 中星历列表的插入顺序输出。

`satellites_state.md` 表格列：

| 卫星编号 | 卫星名称 | 星历来源 | 更新时间 | 定轨时间 (EPOCH) | 上一次更新状态 | 这一次更新状态 |
|---|---|---|---|---|---|---|

其中：

- `更新时间`：本地缓存被新增或替换的时间。
- `定轨时间 (EPOCH)`：星历数据自带的轨道历元时间。
- 判断两份轨道数据哪个更新，只比较 `EPOCH`，不比较 `更新时间`。
- JSON、KVN、CSV、XML 和 TLE 转换都会保留并转换 `EPOCH`。

状态包括：`成功新增`、`成功更新`、`星历源与缓存一致`、`星历源比缓存更旧`、`失败`、`失败（使用缓存）`、`未处理`。

## 删除缓存记录

使用 `--delete-id` 删除 `satellites.pkl` 中的星历记录，支持：

- NORAD 编号
- TLE 中实际使用的编号或别名
- INTDES

示例：

```bash
python main.py --delete-id 25544
python main.py --delete-id TLE:70000
python main.py --delete-id INTDES:2020-025
python main.py --delete-id 25544 --delete-id INTDES:2020-025
```

删除时同步清理 `aliases`、`sources`、`status`、`timestamps`，并覆盖更新 `logs.txt` 和 `satellites_state.md`。

注意：`--delete-id` 不修改 `satellitelists/*.json`。如果该卫星仍在任何列表文件中，下一次普通更新会重新加入。

## 大编号映射

- `NORAD_CAT_ID <= 69999`：TLE 中保留原编号。
- `90000 <= NORAD_CAT_ID <= 99999`：视为临时/特殊编号，保留原编号。
- 其他 `NORAD_CAT_ID > 69999`：按 `satellites.pkl` 中的顺序分配稳定别名 `70000..89999`。
- 原始 `NORAD_CAT_ID` 始终保留在 OMM、JSON、KVN、CSV、XML 中；只有 TLE 行使用别名。
- 分配时跳过列表中已有的 5 位真实编号，避免同一列表内编号冲突。
- 新增卫星追加到星历列表末尾；已有卫星在原位置替换，因此别名不会因普通更新而漂移。

## 安装

- Python 3.10 或更高版本。
- 无第三方运行库，不需要安装 `requests`。

## 运行

```bash
python main.py
```

离线仅使用本地文件：

```bash
python main.py --offline --source localtle --source localjson
```

只测试少量卫星：

```bash
python main.py --limit 3
```

指定代理或源顺序：

```bash
python main.py --proxy http://PROXY_HOST:PROXY_PORT --source celestrak --source satnogs --source localtle --source localjson
```

环境变量：

- `AUTOTLE_PROXY`
- `AUTOTLE_SOURCES`，例如 `celestrak,satnogs,localtle,localjson`
- `AUTOTLE_CELESTRAK_FORMATS`，例如 `JSON,KVN,CSV,XML,TLE`
- `AUTOTLE_TIMEOUT`
- `AUTOTLE_RETRIES`
- `AUTOTLE_STATE`
- `AUTOTLE_OUTPUT_DIR`

## 测试

```bash
python -m unittest discover -s tests -v
```

无第三方 Python 依赖，使用标准库运行。

## 数据格式参考

- CelesTrak GP data formats: <https://celestrak.org/NORAD/documentation/gp-data-formats.php>
- SatNOGS DB API: <https://db.satnogs.org/api/>
- SatNOGS TLE API: <https://db.satnogs.org/api/tle/>

SatNOGS TLE API 当前只支持 `format=json` 和 `format=3le`；`norad_cat_id` 为整数查询参数，`sat_id` 为字符串查询参数。
