<template>
  <ResourceCatalogPage
    resource="agent"
    title="智能体广场"
    subtitle="发现、创建并配置测试智能体"
    action-label="创建智能体"
    search-placeholder="搜索智能体..."
    :fields="fields"
    :card-options="{ showIcon: true, iconName: 'robot' }"
    use-label="使用智能体"
    @use="useAgent"
  />
</template>

<script setup>
import { useRouter } from 'vue-router'

import ResourceCatalogPage from '../components/ResourceCatalogPage.vue'


const router = useRouter()
const fields = [
  { key: 'name', label: '名称', required: true, placeholder: '例如：API 测试专家' },
  { key: 'description', label: '描述', type: 'textarea' },
  { key: 'instructions', label: '系统指令', type: 'textarea', required: true },
  { key: 'category', label: '分类', default: '自定义' },
  { key: 'model_override', label: '模型覆盖', placeholder: '留空使用默认模型' },
  { key: 'allowed_rule_ids', label: '允许的规则 ID', type: 'list' },
  { key: 'allowed_plugin_ids', label: '允许的插件 ID', type: 'list' },
  { key: 'allowed_document_ids', label: '允许的文档 ID', type: 'list' },
]

function useAgent(agent) {
  router.push({ name: 'Home', query: { agent_id: agent.id } })
}
</script>
