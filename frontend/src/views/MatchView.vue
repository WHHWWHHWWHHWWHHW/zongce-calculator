<script setup lang="ts">
import { ElMessage, type TableInstance, type UploadRequestOptions } from 'element-plus'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import YearSelect from '@/components/YearSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useYearStore } from '@/stores/year'
import { errorMessage } from '@/utils/errors'
import {
  canConfirm,
  MATCH_STATUS,
  matchableItems,
  ROUTE_LABEL,
  ROUTE_TAG,
  selectedDeclarations,
  type Suggestion,
} from '@/utils/match'

const auth = useAuthStore()
const years = useYearStore()
const status = ref<Schemas['AiStatus'] | null>(null)
const catalog = ref<Schemas['AbilityCatalog'] | null>(null)
const form = reactive({ catalogCode: '', context: '' })
const result = ref<Schemas['AwardMatchResult'] | null>(null)
const source = ref('')
const selection = ref<Suggestion[]>([])
const confirmed = ref<Schemas['FastTrackItem'][]>([])
const busy = ref(false)
const table = ref<TableInstance>()

const items = computed(() => matchableItems(catalog.value))
const toConfirm = computed(() => selectedDeclarations(selection.value))

onMounted(async () => {
  try {
    status.value = unwrap(await auth.api.GET('/api/v1/ai/status'))
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
})

watch(
  () => years.selectedId,
  async (id) => {
    result.value = null
    catalog.value = null
    if (id === null) return
    try {
      catalog.value = unwrap(
        await auth.api.GET('/api/v1/years/{year_id}/catalog', {
          params: { path: { year_id: id } },
        }),
      )
    } catch (e) {
      ElMessage.error(errorMessage(e))
    }
  },
  { immediate: true },
)

async function upload(options: UploadRequestOptions): Promise<void> {
  if (years.selectedId === null || !form.catalogCode) {
    ElMessage.warning('请先选择学年和申报项目')
    return
  }
  const file = options.file
  busy.value = true
  confirmed.value = []
  try {
    result.value = unwrap(
      await auth.api.POST('/api/v1/years/{year_id}/ai/award-match', {
        params: { path: { year_id: years.selectedId } },
        body: { file: '', catalog_code: form.catalogCode, context: form.context },
        bodySerializer: () => {
          const data = new FormData()
          data.append('file', file, file.name)
          data.append('catalog_code', form.catalogCode)
          data.append('context', form.context)
          return data
        },
      }),
    )
    source.value = file.name
    await nextTick()
    for (const row of result.value.suggestions) {
      if (canConfirm(row)) table.value?.toggleRowSelection(row, true)
    }
  } catch (e) {
    result.value = null
    ElMessage.error(errorMessage(e))
  } finally {
    busy.value = false
  }
}

async function confirm(): Promise<void> {
  if (years.selectedId === null || toConfirm.value.length === 0) return
  busy.value = true
  try {
    const done = unwrap(
      await auth.api.POST('/api/v1/years/{year_id}/ai/fast-track', {
        params: { path: { year_id: years.selectedId } },
        body: { declaration_ids: toConfirm.value, source: source.value },
      }),
    )
    confirmed.value = done.items
    table.value?.clearSelection()
    const failed = done.items.length - done.approved
    ElMessage[failed ? 'warning' : 'success'](
      `已通过 ${done.approved} 条${failed ? `，${failed} 条未通过（见下方说明）` : ''}`,
    )
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    busy.value = false
  }
}

const doneIds = computed(
  () => new Set(confirmed.value.filter((i) => i.ok).map((i) => i.declaration_id)),
)
const selectable = (row: Suggestion) =>
  canConfirm(row) && !doneIds.value.has(row.declaration_id as number)
</script>

<template>
  <section>
    <h2>名单比对</h2>
    <p class="muted">
      上传学院公布的获奖名单，与待审核的申报逐条比对：Excel / CSV
      名单按学号匹配；各部门的活动获奖名单（带文字的 PDF 或 TXT）按“班级 +
      姓名”找学生、按名单写明的分值对应申报等级。系统只给建议：
      “可快速通过”的条目需要你勾选确认后才会通过，每条都会记入审核记录和审计日志；其余条目请在审核工作台逐条处理。
    </p>
    <p v-if="status" class="muted">
      AI 识别：<el-tag size="small" type="info">{{ status.provider }}</el-tag>
      <span v-if="!status.image_recognition">（支持表格和带文字的 PDF，暂不支持图片和扫描件）</span>
      ；快速通过阈值 {{ status.fast_track_threshold }}
    </p>
    <div class="toolbar">
      <YearSelect />
      <el-select
        v-model="form.catalogCode"
        filterable
        placeholder="申报项目"
        class="item-select"
        aria-label="申报项目"
        data-testid="match-item"
      >
        <el-option v-for="item in items" :key="item.code" :label="item.name" :value="item.code" />
      </el-select>
      <el-input
        v-model="form.context"
        placeholder="整表说明，如：一类赛事 / 校级"
        class="context"
        maxlength="100"
        aria-label="整表共同信息"
        data-testid="match-context"
      />
      <el-upload :show-file-list="false" :http-request="upload" accept=".xlsx,.csv,.pdf,.txt">
        <el-button type="primary" :loading="busy">上传名单并比对</el-button>
      </el-upload>
    </div>

    <template v-if="result">
      <p>
        {{ result.catalog_name }}：
        <el-tag
          v-for="(label, route) in ROUTE_LABEL"
          :key="route"
          :type="ROUTE_TAG[route]"
          class="tag"
        >
          {{ label }} {{ result.counts[route] ?? 0 }}
        </el-tag>
        <span v-if="result.out_of_scope_rows" class="muted">
          另有 {{ result.out_of_scope_rows }} 行不属于本班，未显示。
        </span>
        <span v-if="result.unmatched_declaration_ids.length" class="muted">
          有
          {{ result.unmatched_declaration_ids.length }}
          条待审核申报不在名单中，请在审核工作台照常审核。
        </span>
      </p>
      <div class="toolbar">
        <el-button
          type="success"
          :disabled="!toConfirm.length || busy"
          data-testid="match-confirm"
          @click="confirm"
        >
          确认通过所选（{{ toConfirm.length }} 条）
        </el-button>
      </div>
      <div class="table-scroll">
        <el-table
          ref="table"
          data-testid="match-table"
          :data="result.suggestions"
          size="small"
          row-key="row"
          @selection-change="(rows: Suggestion[]) => (selection = rows)"
        >
          <el-table-column type="selection" width="40" :selectable="selectable" />
          <el-table-column prop="row" label="行" width="56" />
          <el-table-column prop="student_username" label="学号" min-width="110" />
          <el-table-column label="姓名" min-width="90">
            <template #default="{ row }">{{ (row as Suggestion).student_name ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="名单等级" min-width="160">
            <template #default="{ row }">{{
              (row as Suggestion).form_option_name ?? '—'
            }}</template>
          </el-table-column>
          <el-table-column label="申报等级" min-width="160">
            <template #default="{ row }">{{
              (row as Suggestion).declared_option_name ?? '—'
            }}</template>
          </el-table-column>
          <el-table-column label="比对结果" min-width="110">
            <template #default="{ row }">{{ MATCH_STATUS[(row as Suggestion).status] }}</template>
          </el-table-column>
          <el-table-column label="建议" min-width="100">
            <template #default="{ row }">
              <el-tag
                v-if="doneIds.has((row as Suggestion).declaration_id ?? -1)"
                type="success"
                size="small"
              >
                已通过
              </el-tag>
              <el-tag v-else :type="ROUTE_TAG[(row as Suggestion).route]" size="small">
                {{ ROUTE_LABEL[(row as Suggestion).route] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="confidence" label="置信度" width="76" />
          <el-table-column label="说明" min-width="200">
            <template #default="{ row }">{{
              (row as Suggestion).reasons.join('；') || '—'
            }}</template>
          </el-table-column>
        </el-table>
      </div>
      <el-alert
        v-for="item in confirmed.filter((i) => !i.ok)"
        :key="item.declaration_id"
        type="warning"
        :closable="false"
        class="gap"
        :title="`申报 #${item.declaration_id}：${item.message}`"
      />
    </template>
  </section>
</template>

<style scoped>
.item-select {
  width: 240px;
}

.context {
  width: 220px;
}

.tag {
  margin: 0 4px 4px 0;
}

.gap {
  margin-top: 8px;
}

.table-scroll {
  overflow-x: auto;
}

@media (max-width: 600px) {
  .item-select,
  .context {
    width: 100%;
  }
}
</style>
