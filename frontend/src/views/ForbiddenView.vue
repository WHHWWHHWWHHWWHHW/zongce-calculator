<template>
  <div class="page">
    <el-result icon="warning" title="没有权限" sub-title="当前账号无权访问该页面。">
      <template #extra>
        <RouterLink to="/"><el-button type="primary">返回首页</el-button></RouterLink>
      </template>
    </el-result>
  </div>
</template>
