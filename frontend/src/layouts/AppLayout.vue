<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { appRoutes } from '@/router'
import { useAuthStore } from '@/stores/auth'
import { ROLE_NAMES } from '@/utils/format'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const menu = computed(() =>
  auth.mustChangePassword
    ? []
    : appRoutes.filter(
        (r) => r.meta?.menu && (!r.meta.roles || auth.hasRole(...(r.meta.roles ?? []))),
      ),
)
const roleText = computed(() => auth.roles.map((r) => ROLE_NAMES[r]).join('、'))

async function onCommand(command: string): Promise<void> {
  if (command === 'password') {
    await router.push({ name: 'change-password' })
  } else {
    auth.logout()
    await router.replace({ name: 'login' })
  }
}
</script>

<template>
  <el-container class="layout">
    <el-header class="layout-header">
      <RouterLink to="/" class="brand">综测智能核算平台</RouterLink>
      <el-menu
        mode="horizontal"
        :default-active="String(route.name ?? '')"
        class="layout-menu"
        :ellipsis="true"
        background-color="#1665c7"
        text-color="#dbe7f7"
        active-text-color="#ffffff"
      >
        <el-menu-item
          v-for="item in menu"
          :key="String(item.name)"
          :index="String(item.name)"
          @click="router.push({ name: item.name })"
        >
          {{ item.meta?.title }}
        </el-menu-item>
      </el-menu>
      <el-dropdown trigger="click" @command="onCommand">
        <span class="user" data-testid="user-menu">
          {{ auth.user?.name }}
          <span class="muted user-role">{{ roleText }}</span>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="password">修改密码</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </el-header>
    <el-main class="layout-main">
      <RouterView />
    </el-main>
  </el-container>
</template>

<style scoped>
.layout-header {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 56px;
  background: var(--el-color-primary);
  padding: 0 16px;
  color: #fff;
}

.brand {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #fff;
  text-decoration: none;
  white-space: nowrap;
}

.layout-menu {
  flex: 1;
  min-width: 0;
  height: 56px;
  border-bottom: none;
  --el-menu-hover-bg-color: #12519f;
}

.layout-menu :deep(.el-menu-item.is-active) {
  border-bottom: 3px solid #fff;
}

.user {
  cursor: pointer;
  white-space: nowrap;
  color: #fff;
}

.user-role {
  color: #dbe7f7;
  margin-left: 4px;
}

.layout-main {
  padding: 0;
}

@media (max-width: 600px) {
  .layout-header {
    padding: 0 8px;
    gap: 4px;
  }

  .brand,
  .user-role {
    display: none;
  }
}
</style>
