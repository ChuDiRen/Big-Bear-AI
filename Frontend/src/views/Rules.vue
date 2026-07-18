<template>
  <ResourceCatalogPage
    resource="rule"
    title="规则市场"
    subtitle="探索和管理您的测试规则"
    action-label="新建规则"
    search-placeholder="搜索规则..."
    :fields="fields"
    :card-options="{ showIcon: true, iconName: 'scroll' }"
    use-label="在对话中使用"
    @use="useRule"
  />
</template>

<script setup>
import { useRouter } from 'vue-router'

import ResourceCatalogPage from '../components/ResourceCatalogPage.vue'


const router = useRouter()
const fields = [
  { key: 'title', label: '名称', required: true, placeholder: '例如：API 契约检查' },
  { key: 'description', label: '描述', type: 'textarea' },
  { key: 'definition', label: '规则定义', type: 'textarea', required: true },
  { key: 'tags', label: '标签', type: 'list', placeholder: 'API, 安全' },
  { key: 'enabled', label: '启用', type: 'checkbox', default: true },
]

function useRule(rule) {
  router.push({ name: 'Home', query: { rule_id: rule.id } })
}
</script>
