import csv
import io
from collections import Counter
from itertools import islice

from catalog.product_csv import spreadsheet_text

MAX_BYTES = 256 * 1024
MAX_ROWS = 500


def parse_upload(upload):
    if not upload or upload.size > MAX_BYTES:
        raise ValueError("请选择 256 KiB 以内的 CSV 文件。")
    try:
        raw = upload.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("文件超过 256 KiB。")
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
        if next(reader, None) != ["sku", "stock"]:
            raise ValueError("表头必须是 sku,stock，顺序固定。")
        records = list(islice(reader, MAX_ROWS + 1))
        if len(records) > MAX_ROWS:
            raise ValueError("每个文件最多 500 条数据。")
        counts = Counter(fields[0] for fields in records if fields)
        items, errors = [], []
        for number, fields in enumerate(records, start=2):
            sku = fields[0] if fields else ""
            if len(fields) != 2:
                error = "需要两列。"
            elif not sku or len(sku) > 40 or spreadsheet_text(sku) != sku:
                error = "SKU 无效。"
            elif counts[sku] > 1:
                error = "SKU 在文件中重复。"
            elif not (fields[1].isascii() and fields[1].isdigit() and len(fields[1]) <= 10
                      and int(fields[1]) <= 2147483647):
                error = "库存须为 0 至 2147483647 的整数。"
            else:
                items.append((number, sku, int(fields[1])))
                error = None
            if error:
                errors.append([number, sku[:40], error])
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("请使用有效的 UTF-8 CSV。") from exc
    if not items and not errors:
        raise ValueError("文件至少需要一条数据。")
    return items, errors
