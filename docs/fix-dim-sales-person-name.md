# dbt 模型修复: dim_sales_person 缺少姓名列

## 问题

查询"销售员有哪些人"时，LLM 找不到销售员的姓名。

## 根因

`dim_sales_person` 表中没有 `full_name` 列：
- 当前有: `business_entity_id`, `territory_id`, `sales_quota`, `bonus`, `commission_pct`, `sales_ytd`, `sales_last_year`
- 缺少: `full_name` 或 `first_name` + `last_name`

同样 `dim_employee` 也没有姓名列。

姓名数据实际上存在于 staging 和 intermediate 层（`stg_person`、`int_person_detail`、`int_sales_person_detail`），但在生成 dim 表时没带过来。

## 修复方案

在 `dim_sales_person` 的 dbt 模型中，从 `stg_person` 或 `int_person_detail` 关联 `full_name` 字段：

```sql
-- 在 dim_sales_person.sql 中添加
WITH sales_person_base AS (
    SELECT * FROM {{ ref('stg_salesperson') }}
),
person_names AS (
    SELECT 
        business_entity_id,
        full_name,
        first_name,
        last_name
    FROM {{ ref('int_person_detail') }}
)
SELECT 
    sp.business_entity_id,
    pn.full_name,
    pn.first_name,
    pn.last_name,
    sp.territory_id,
    sp.sales_quota,
    sp.bonus,
    sp.commission_pct,
    sp.sales_ytd,
    sp.sales_last_year
FROM sales_person_base sp
LEFT JOIN person_names pn 
    ON sp.business_entity_id = pn.business_entity_id
```

同样逻辑也适用于 `dim_employee`。

## 受影响表

- `dim_sales_person` → 加 `full_name`, `first_name`, `last_name`
- `dim_employee` → 加 `full_name`, `first_name`, `last_name`

## 修复后效果

修复后 Shuyu 的 filter 可以改回 `dim_*,fct_*`，不需要 `int_person*` 白名单了。LLM 可以直接在 `dim_sales_person` 查到姓名。
