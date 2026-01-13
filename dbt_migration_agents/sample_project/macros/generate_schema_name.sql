{% macro generate_schema_name(custom_schema_name, node) -%}
    {#
        Use the custom schema name directly without prefixing with target schema.
        This allows models to be placed in bronze/silver/gold schemas directly.
    #}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
