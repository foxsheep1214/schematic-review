# 改版网表 Diff 与历史意见闭环

先分别解析旧版和新版网表，再运行：

    python3 scripts/diff_netlists.py old-db.json new-db.json \
      --claims review-claims.json --json diff.json --fail-on-open-claims

Diff 自动列出器件新增/删除/字段变化、引脚换网和网络成员变化。工具伪网络默认不参与
网络成员 Diff，但引脚从伪 NC 转入真实网络等变化仍会出现在 pin change 中。

## 闭环断言格式

claim id 必须唯一；ref/node/net/field 等定位字段必须完整，字段名仅允许
part、value、jedec、prim、nc。声明结构不合法时工具直接退出，不进入闭环判定。

    {
      "schema_version": 1,
      "claims": [
        {
          "id": "F-05",
          "description": "U10 器件档位已改为 RTL8326BI",
          "expect": [
            {"kind": "part_field_changed", "ref": "U10", "field": "part"},
            {
              "kind": "part_field_equals",
              "ref": "U10",
              "field": "part",
              "value": "RTL8326BI"
            }
          ]
        },
        {
          "id": "F-07",
          "description": "U3.8 已从 3V3 上拉改到下拉网络",
          "expect": [
            {"kind": "pin_net_changed", "node": "U3.8"},
            {"kind": "pin_net_equals", "node": "U3.8", "net": "BOOT0_PD"}
          ]
        }
      ]
    }

支持的 kind：

- part_added / part_removed
- part_field_changed / part_field_equals
- pin_net_changed / pin_net_equals
- net_membership_changed

一条历史意见只有在其全部断言通过时才是真闭环；否则输出 Rule-17 FINDING。
