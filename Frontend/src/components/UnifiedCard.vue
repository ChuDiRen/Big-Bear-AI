<template>
  <button
    type="button"
    class="card unified-card"
    :style="cardStyle"
    @click="emit('select', item)"
  >
    <i
      data-card-icon
      aria-hidden="true"
      class="ph-fill card-decoration-icon"
      :class="`ph-${safeIcon}`"
    ></i>

    <span class="card-header">
      <span class="badge-list">
        <span v-if="badgeText" class="badge" :style="badgeStyle">{{ badgeText }}</span>
        <span
          v-for="tag in extraBadges"
          :key="tag"
          class="badge"
          :style="badgeStyle"
        >
          {{ tag }}
        </span>
      </span>
      <span v-if="statusText" class="mcp-status" :class="statusClass">
        <span class="status-dot"></span>
        {{ statusText }}
      </span>
    </span>

    <span class="card-title">{{ title }}</span>
    <span class="card-desc">{{ description }}</span>

    <span class="card-footer">
      <span class="author-info">
        <span class="avatar-sm" :style="avatarStyle">{{ authorInitial }}</span>
        <span>{{ author }}<template v-if="date"> · {{ date }}</template></span>
      </span>
    </span>
  </button>
</template>

<script setup>
import { computed } from 'vue'


const SAFE_ICONS = new Set([
  'arrows-clockwise',
  'book-open',
  'bug',
  'check-square',
  'code',
  'database',
  'device-mobile',
  'file-doc',
  'file-text',
  'folder',
  'gauge',
  'github-logo',
  'globe',
  'google-drive-logo',
  'lightbulb',
  'magnifying-glass',
  'plugs-connected',
  'puzzle-piece',
  'robot',
  'scroll',
  'shield-check',
  'slack-logo',
  'star',
  'test-tube',
])

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
  options: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['select'])

const title = computed(() => props.item.title ?? props.item.name ?? '未命名')
const description = computed(() => props.item.description ?? props.item.desc ?? '')
const author = computed(() => props.item.author ?? '大熊AI')
const authorInitial = computed(() => author.value.slice(0, 1).toUpperCase())
const date = computed(() => {
  const value = props.item.updated_at ?? props.item.date ?? ''
  return value ? String(value).slice(0, 10) : ''
})
const badgeText = computed(() => (
  props.options.badgeText
  ?? props.item.category
  ?? props.item.type
  ?? props.item.tags?.[0]
  ?? ''
))
const extraBadges = computed(() => props.options.extraBadges ?? props.item.tags?.slice(1) ?? [])
const statusText = computed(() => (
  props.options.statusText
  ?? props.item.health_status
  ?? props.item.status_label
  ?? props.item.status
  ?? ''
))
const statusClass = computed(() => String(statusText.value).toLowerCase().replace(/[^a-z]+/g, '-'))
const requestedIcon = computed(() => props.options.iconName ?? props.item.icon ?? 'star')
const safeIcon = computed(() => SAFE_ICONS.has(requestedIcon.value) ? requestedIcon.value : 'star')
const accent = computed(() => safeColor(props.item.textColor, '#2563EB'))
const tint = computed(() => safeColor(props.item.color, '#E8F0FE'))
const cardStyle = computed(() => ({
  '--card-accent': accent.value,
  '--card-tint': tint.value,
}))
const badgeStyle = computed(() => ({ backgroundColor: tint.value, color: accent.value }))
const avatarStyle = computed(() => ({ backgroundColor: accent.value }))

function safeColor(value, fallback) {
  return typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value) ? value : fallback
}
</script>

<style scoped>
.unified-card {
  position: relative;
  min-height: 180px;
  width: 100%;
  overflow: hidden;
  text-align: left;
  color: inherit;
  background: linear-gradient(145deg, color-mix(in srgb, var(--card-tint) 70%, white), white 72%);
}

.unified-card:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--card-accent) 35%, transparent);
  outline-offset: 2px;
}

.card-decoration-icon {
  position: absolute;
  top: 14px;
  right: 14px;
  color: var(--card-accent);
  font-size: 2rem;
  opacity: 0.18;
}

.card-header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.badge-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.badge {
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
}

.card-title {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 14px;
  font-size: 1rem;
  font-weight: 650;
}

.card-desc {
  position: relative;
  z-index: 1;
  display: -webkit-box;
  flex: 1;
  margin-top: 8px;
  overflow: hidden;
  color: #5f6570;
  font-size: 0.85rem;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.card-footer {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: auto;
  padding-top: 14px;
}

.author-info,
.avatar-sm {
  display: flex;
  align-items: center;
}

.author-info {
  gap: 7px;
  color: #747b87;
  font-size: 0.78rem;
}

.avatar-sm {
  width: 22px;
  height: 22px;
  justify-content: center;
  border-radius: 50%;
  color: white;
  font-size: 0.68rem;
  font-weight: 700;
}
</style>
