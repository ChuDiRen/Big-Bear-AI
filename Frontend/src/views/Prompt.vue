<template>
  <ResourceCatalogPage
    resource="prompt"
    title="Prompt 库"
    subtitle="创建和复用测试提示词模板"
    action-label="新建 Prompt"
    search-placeholder="搜索 Prompt..."
    :fields="fields"
    :card-options="{ showIcon: true, iconName: 'file-text' }"
    use-label="在对话中使用"
    @use="usePrompt"
  />
</template>

<script setup>
import { useRouter } from 'vue-router'

import ResourceCatalogPage from '../components/ResourceCatalogPage.vue'


const router = useRouter()
const fields = [
  { key: 'title', label: '名称', required: true, placeholder: '例如：生成接口测试' },
  { key: 'description', label: '描述', type: 'textarea' },
  { key: 'template', label: '提示词模板', type: 'textarea', required: true },
  { key: 'variables', label: '变量', type: 'list', placeholder: 'endpoint, schema' },
  { key: 'tags', label: '标签', type: 'list', placeholder: 'API, 代码生成' },
]

function usePrompt(prompt) {
  router.push({ name: 'Home', query: { prompt_id: prompt.id } })
}
</script>
