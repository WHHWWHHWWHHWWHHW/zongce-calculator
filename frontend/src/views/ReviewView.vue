<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'

import { type Schemas, unwrap } from '@/api/client'
import EvidenceDialog from '@/components/EvidenceDialog.vue'
import ReviewHistory from '@/components/ReviewHistory.vue'
import YearSelect from '@/components/YearSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { useYearStore } from '@/stores/year'
import {
  type Catalog,
  type Declaration,
  findItem,
  itemName,
  optionName,
  reviewFlags,
} from '@/utils/catalog'
import { errorMessage } from '@/utils/errors'
import { DECLARATION_STATUS, sameDecimal, scoreText } from '@/utils/format'

type Status = Schemas['DeclarationStatus']
type Action = Schemas['ReviewAction']

const auth = useAuthStore()
const years = useYearStore()
const isAdmin = computed(() => auth.hasRole('college_admin'))
const catalog = ref<Catalog | null>(null)
const rows = ref<Declaration[]>([])
const loading = ref(false)
const filter = reactive({ status: 'submitted' as Status | '', className: '' })
const evidenceOpen = ref(false)
const evidenceOf = ref<Declaration | null>(null)
const dialog = reactive({
  open: false,
  action: 'approve' as Action,
  target: null as Declaration | null,
  score: '',
  reason: '',
  busy: false,
})

const ACTIONS: Record<Action, string> = { approve: '通过', adjust: '改分', reject: '驳回' }

async function load(): Promise<void> {
  if (years.selectedId === null) return
  loading.value = true
  try {
    const query = {
      year_id: years.selectedId,
      ...(filter.status ? { status: filter.status } : {}),
      ...(isAdmin.value && filter.className ? { class_name: filter.className } : {}),
    }
    const [cat, list] = await Promise.all([
      auth.api.GET('/api/v1/years/{year_id}/catalog', {
        params: { path: { year_id: years.selectedId } },
      }),
      auth.api.GET('/api/v1/declarations', { params: { query } }),
    ])
    catalog.value = unwrap(cat)
    rows.value = unwrap(list)
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    loading.value = false
  }
}

watch(() => [years.selectedId, filter.status], load, { immediate: true })

const flagsOf = (d: Declaration) => reviewFlags(d, findItem(catalog.value, d.catalog_code))
const rowClass = ({ row }: { row: Declaration }) =>
  flagsOf(row).length && row.status === 'submitted' ? 'row-discrepant' : ''
const isSelf = (d: Declaration) => d.student_id === auth.user?.id
const canReview = (d: Declaration) =>
  !isSelf(d) && (d.status === 'submitted' || (d.status === 'approved' && isAdmin.value))

function open(d: Declaration, action: Action): void {
  Object.assign(dialog, { open: true, action, target: d, score: '', reason: '' })
}

async function confirm(): Promise<void> {
  const target = dialog.target
  if (!target) return
  if (!dialog.reason.trim()) {
    ElMessage.warning('请填写理由')
    return
  }
  if (dialog.action === 'adjust' && !dialog.score.trim()) {
    ElMessage.warning('请填写改后的分数')
    return
  }
  dialog.busy = true
  try {
    unwrap(
      await auth.api.POST('/api/v1/declarations/{declaration_id}/review', {
        params: { path: { declaration_id: target.id } },
        body: {
          action: dialog.action,
          reason: dialog.reason,
          score: dialog.action === 'adjust' ? dialog.score.trim() : null,
        },
      }),
    )
    ElMessage.success(`已${ACTIONS[dialog.action]}`)
    dialog.open = false
    await load()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    dialog.busy = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>审核工作台</h2>
      <div class="toolbar">
        <YearSelect />
        <el-select v-model="filter.status" style="width: 120px" placeholder="状态">
          <el-option label="全部" value="" />
          <el-option
            v-for="(s, key) in DECLARATION_STATUS"
            :key="key"
            :label="s.label"
            :value="key"
          />
        </el-select>
        <el-input
          v-if="isAdmin"
          v-model.trim="filter.className"
          placeholder="班级（全部）"
          style="width: 140px"
          clearable
          @change="load"
        />
      </div>
    </div>
    <p class="muted">标红的行需要重点核对：申报分与建议分不一致、需人工给分或未上传材料。</p>
    <el-table
      v-loading="loading"
      :data="rows"
      :row-class-name="rowClass"
      empty-text="没有符合条件的申报"
      data-testid="review-table"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="expand">
            <p>{{ row.description || '（无说明）' }}</p>
            <p v-if="row.team_size" class="muted">
              完成人数 {{ row.team_size }}，本人位次 {{ row.team_position }}
            </p>
            <ReviewHistory :declaration-id="row.id" />
          </div>
        </template>
      </el-table-column>
      <el-table-column label="学生" min-width="110">
        <template #default="{ row }">
          <div>{{ row.student_name }}</div>
          <div class="muted">{{ row.student_username }} {{ isAdmin ? row.class_name : '' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="项目" min-width="160">
        <template #default="{ row }">
          <div>{{ itemName(catalog, row.catalog_code) }}</div>
          <div class="muted">{{ optionName(catalog, row.catalog_code, row.option_code) }}</div>
          <div>{{ row.title }}</div>
        </template>
      </el-table-column>
      <el-table-column label="建议分" width="84" class-name="score">
        <template #default="{ row }">{{ scoreText(row.suggested_score) }}</template>
      </el-table-column>
      <el-table-column label="申报分" width="84" class-name="score">
        <template #default="{ row }">
          <span
            :class="{
              diff:
                row.claimed_score != null &&
                row.suggested_score != null &&
                !sameDecimal(row.claimed_score, row.suggested_score),
            }"
          >
            {{ scoreText(row.claimed_score) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="审核分" width="84" class-name="score">
        <template #default="{ row }">{{ scoreText(row.approved_score) }}</template>
      </el-table-column>
      <el-table-column label="状态 / 提示" min-width="150">
        <template #default="{ row }">
          <el-tag :type="DECLARATION_STATUS[row.status as Status].type as never" size="small">
            {{ DECLARATION_STATUS[row.status as Status].label }}
          </el-tag>
          <div v-for="flag in flagsOf(row as Declaration)" :key="flag" class="diff flag">
            {{ flag }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            @click="((evidenceOf = row as Declaration), (evidenceOpen = true))"
          >
            材料({{ row.evidence.length }})
          </el-button>
          <template v-if="canReview(row as Declaration)">
            <el-button
              v-if="row.status === 'submitted'"
              link
              type="success"
              data-testid="review-approve"
              @click="open(row as Declaration, 'approve')"
            >
              通过
            </el-button>
            <el-button link type="warning" @click="open(row as Declaration, 'adjust')"
              >改分</el-button
            >
            <el-button
              v-if="row.status === 'submitted'"
              link
              type="danger"
              @click="open(row as Declaration, 'reject')"
            >
              驳回
            </el-button>
          </template>
          <span v-else-if="isSelf(row as Declaration)" class="muted">本人申报</span>
        </template>
      </el-table-column>
    </el-table>

    <EvidenceDialog v-model="evidenceOpen" :declaration="evidenceOf" :editable="false" />

    <el-dialog v-model="dialog.open" :title="ACTIONS[dialog.action]" width="480px">
      <el-form label-width="80px" @submit.prevent="confirm">
        <el-form-item v-if="dialog.target" label="申报">
          {{ dialog.target.student_name }} · {{ dialog.target.title }}
        </el-form-item>
        <el-form-item v-if="dialog.action === 'approve'" label="得分">
          {{ dialog.target?.suggested_score ?? dialog.target?.claimed_score ?? '—' }}
          <span class="muted">（建议分，无建议分时取申报分）</span>
        </el-form-item>
        <el-form-item v-if="dialog.action === 'adjust'" label="改为" required>
          <el-input v-model="dialog.score" placeholder="如 3" style="max-width: 160px" />
        </el-form-item>
        <el-form-item label="理由" required>
          <el-input
            v-model="dialog.reason"
            type="textarea"
            :rows="3"
            maxlength="1000"
            data-testid="review-reason"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.open = false">取消</el-button>
        <el-button
          type="primary"
          :loading="dialog.busy"
          data-testid="review-confirm"
          @click="confirm"
        >
          确认{{ ACTIONS[dialog.action] }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.expand {
  padding: 0 16px;
}

.flag {
  font-size: 12px;
}
</style>
