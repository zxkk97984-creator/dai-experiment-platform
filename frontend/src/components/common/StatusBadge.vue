<script setup>
defineProps({ label: String, color: { type: String, default: 'neutral' } })
</script>
<template>
  <span class="badge" :class="'badge-' + color">{{ label }}</span>
</template>
