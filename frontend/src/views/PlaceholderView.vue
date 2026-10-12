<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <main>
    <h1>{{ route.meta.title }}</h1>
    <p>该页面将在组件库选定后实现。</p>
  </main>
</template>
