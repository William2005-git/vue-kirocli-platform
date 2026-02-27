<template>
  <div>
    <h2>设置</h2>
    <a-tabs v-model:activeKey="activeTab">
      <!-- ── Tab 1: 个人信息 ── -->
      <a-tab-pane key="profile" tab="个人信息">
        <a-row :gutter="24">
          <a-col :span="12">
            <a-card title="基本信息" style="margin-bottom: 24px">
              <a-descriptions :column="1" bordered>
                <a-descriptions-item label="用户名">{{ user?.username }}</a-descriptions-item>
                <a-descriptions-item label="邮箱">{{ user?.email }}</a-descriptions-item>
                <a-descriptions-item label="姓名">{{ user?.full_name || '-' }}</a-descriptions-item>
                <a-descriptions-item label="角色">
                  <a-tag :color="user?.role === 'admin' ? 'red' : 'blue'">
                    {{ user?.role === 'admin' ? '管理员' : '普通用户' }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="所属组">
                  <a-space wrap>
                    <a-tag v-for="g in user?.groups" :key="g">{{ g }}</a-tag>
                    <span v-if="!user?.groups?.length">-</span>
                  </a-space>
                </a-descriptions-item>
              </a-descriptions>
            </a-card>
            <a-card title="我的配额">
              <a-descriptions :column="1" bordered>
                <a-descriptions-item label="最大并发会话数">
                  {{ user?.permissions?.max_concurrent_sessions ?? 3 }}
                </a-descriptions-item>
                <a-descriptions-item label="单次会话最长时长">
                  {{ user?.permissions?.max_session_duration_hours ?? 2 }} 小时
                </a-descriptions-item>
                <a-descriptions-item label="每日会话配额">
                  {{ user?.permissions?.daily_session_quota ?? 10 }}
                </a-descriptions-item>
              </a-descriptions>
            </a-card>
          </a-col>
          <a-col :span="12">
            <a-card title="偏好设置">
              <a-form :model="prefForm" layout="vertical" @finish="savePref">
                <a-form-item label="界面语言">
                  <a-select v-model:value="prefForm.language" style="width: 100%">
                    <a-select-option value="zh-CN">中文（简体）</a-select-option>
                    <a-select-option value="en-US">English</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item label="主题">
                  <a-radio-group v-model:value="prefForm.theme">
                    <a-radio-button value="light">浅色</a-radio-button>
                    <a-radio-button value="dark">深色</a-radio-button>
                  </a-radio-group>
                </a-form-item>
                <a-form-item label="时区">
                  <a-select v-model:value="prefForm.timezone" style="width: 100%" show-search>
                    <a-select-option v-for="tz in timezones" :key="tz" :value="tz">{{ tz }}</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item>
                  <a-button type="primary" html-type="submit" :loading="prefSaving">保存设置</a-button>
                </a-form-item>
              </a-form>
            </a-card>
          </a-col>
        </a-row>
      </a-tab-pane>

      <!-- ── Tab 2: 我的设备 ── -->
      <a-tab-pane key="devices" tab="我的设备">
        <a-card>
          <template #title>
            我的已知设备
            <a-typography-text type="secondary" style="font-size: 13px; margin-left: 8px">
              系统会在您首次从新设备登录时发送通知
            </a-typography-text>
          </template>
          <a-table
            :columns="deviceColumns"
            :data-source="devices"
            :loading="devicesLoading"
            row-key="id"
            :row-class-name="(r: UserDevice) => r.is_current ? 'current-device-row' : ''"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }: { column: { key: string }, record: UserDevice }">
              <template v-if="column.key === 'device_name'">
                <a-space v-if="editingDeviceId !== record.id">
                  <span>{{ record.device_name }}</span>
                  <a-tag v-if="record.is_current" color="blue">当前设备</a-tag>
                </a-space>
                <a-input
                  v-else
                  v-model:value="editingDeviceName"
                  size="small"
                  style="width: 160px"
                  @pressEnter="saveDeviceName(record.id)"
                />
              </template>
              <template v-else-if="column.key === 'fingerprint_preview'">
                <a-tooltip :title="record.fingerprint_preview">
                  <span style="font-family: monospace">{{ record.fingerprint_preview.slice(0, 8) }}</span>
                </a-tooltip>
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-space v-if="editingDeviceId !== record.id">
                  <a-button type="link" size="small" @click="startEditDevice(record)">重命名</a-button>
                  <a-tooltip :title="record.is_current ? '不能删除当前设备' : ''">
                    <a-popconfirm
                      title="确定删除此设备记录？下次从该设备登录将再次触发新设备通知。"
                      :disabled="record.is_current"
                      @confirm="handleDeleteDevice(record.id)"
                    >
                      <a-button type="link" size="small" danger :disabled="record.is_current">删除</a-button>
                    </a-popconfirm>
                  </a-tooltip>
                </a-space>
                <a-space v-else>
                  <a-button type="link" size="small" @click="saveDeviceName(record.id)">保存</a-button>
                  <a-button type="link" size="small" @click="cancelEditDevice">取消</a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-tab-pane>

      <!-- ── Tab 3: IP 白名单（仅管理员）── -->
      <a-tab-pane v-if="isAdmin" key="whitelist" tab="IP 白名单">
        <a-card>
          <a-alert
            message="启用后，只有白名单内的 IP 才能访问平台。请确保您的当前 IP 在白名单中，否则保存后将无法访问。"
            type="warning"
            show-icon
            style="margin-bottom: 16px"
          />
          <a-space direction="vertical" style="width: 100%">
            <a-space>
              <span>启用白名单：</span>
              <a-switch v-model:checked="wlEnabled" checked-children="已启用" un-checked-children="已禁用" @change="handleWLEnabledChange" />
              <a-typography-text v-if="!wlEnabled" type="secondary">当前所有 IP 均可访问</a-typography-text>
            </a-space>
            <a-space>
              <span>您的当前 IP：</span>
              <a-tag>{{ myIP || '获取中...' }}</a-tag>
              <a-button
                size="small"
                :disabled="myIPInList"
                @click="addMyIPToList"
              >
                {{ myIPInList ? '已在白名单中' : '添加到白名单' }}
              </a-button>
            </a-space>
          </a-space>

          <a-divider />

          <div style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center">
            <span>白名单条目</span>
            <a-button size="small" type="dashed" @click="addWLEntry">+ 添加条目</a-button>
          </div>

          <a-table
            :data-source="wlEntries"
            :columns="wlColumns"
            row-key="key"
            :pagination="false"
            :locale="{ emptyText: '暂无条目，所有 IP 均被拒绝（启用时）' }"
          >
            <template #bodyCell="{ column, record }: { column: { key: string }, record: WLEntry }">
              <template v-if="column.key === 'cidr'">
                <a-input
                  v-model:value="record.cidr"
                  placeholder="如 203.0.113.0/24"
                  :status="record.cidrError ? 'error' : ''"
                  @blur="validateCIDR(record)"
                />
                <div v-if="record.cidrError" style="color: #ff4d4f; font-size: 12px">{{ record.cidrError }}</div>
              </template>
              <template v-else-if="column.key === 'note'">
                <a-input v-model:value="record.note" placeholder="备注说明（可选）" />
              </template>
              <template v-else-if="column.key === 'actions'">
                <a-button type="link" danger size="small" @click="removeWLEntry(record.key)">删除</a-button>
              </template>
            </template>
          </a-table>

          <div style="margin-top: 16px">
            <a-button type="primary" :loading="wlSaving" @click="saveWhitelist">保存配置</a-button>
          </div>
        </a-card>

        <!-- 自锁警告对话框 -->
        <a-modal
          v-model:open="wlLockWarning"
          title="⚠️ 警告：当前 IP 不在白名单中"
          ok-text="确认保存"
          cancel-text="取消"
          :ok-button-props="{ danger: true }"
          @ok="doSaveWhitelist"
        >
          <p>您的当前 IP <strong>{{ myIP }}</strong> 不在新白名单中。</p>
          <p>保存后您将无法通过浏览器访问平台，只能通过 SSH 登录 EC2 手动修复。</p>
          <p>确定要继续吗？</p>
        </a-modal>
      </a-tab-pane>

      <!-- ── Tab 4: 告警规则（仅管理员）── -->
      <a-tab-pane v-if="isAdmin" key="alerts" tab="告警规则">
        <a-card title="SNS 通知配置" style="margin-bottom: 16px">
          <a-space>
            <a-input
              v-model:value="alertConfig.sns_topic_arn"
              placeholder="arn:aws-cn:sns:cn-north-1:123456789:kirocli-alerts"
              style="width: 480px"
            />
            <a-button type="primary" :loading="alertSaving" @click="saveAlertRules">保存</a-button>
            <a-button :loading="snsTesting" @click="testSNS">测试发送</a-button>
          </a-space>
        </a-card>

        <a-card title="非工作时间段" style="margin-bottom: 16px">
          <a-space wrap>
            <span>开始时间：</span>
            <a-time-picker v-model:value="offhourStart" format="HH:mm" value-format="HH:mm" />
            <span>结束时间：</span>
            <a-time-picker v-model:value="offhourEnd" format="HH:mm" value-format="HH:mm" />
            <span>时区：</span>
            <a-select v-model:value="alertConfig.offhour_tz" style="width: 200px" show-search>
              <a-select-option v-for="tz in timezones" :key="tz" :value="tz">{{ tz }}</a-select-option>
            </a-select>
            <span>冷却期：</span>
            <a-input-number v-model:value="alertConfig.cooldown_minutes" :min="1" :max="1440" addon-after="分钟" />
          </a-space>
        </a-card>

        <a-card title="告警规则配置">
          <a-table
            :data-source="alertRules"
            :columns="alertRuleColumns"
            row-key="rule_key"
            :pagination="false"
          >
            <template #bodyCell="{ column, record }: { column: { key: string }, record: AlertRuleRow }">
              <template v-if="column.key === 'time_window_minutes'">
                <a-input-number
                  v-model:value="record.time_window_minutes"
                  :min="1"
                  :disabled="record.rule_key === 'offhour_login'"
                  addon-after="分钟"
                  style="width: 120px"
                />
              </template>
              <template v-else-if="column.key === 'threshold'">
                <a-input-number
                  v-model:value="record.threshold"
                  :min="1"
                  :disabled="record.rule_key === 'offhour_login'"
                  style="width: 80px"
                />
              </template>
              <template v-else-if="column.key === 'enabled'">
                <a-switch v-model:checked="record.enabled" />
              </template>
            </template>
          </a-table>
          <div style="margin-top: 16px">
            <a-button type="primary" :loading="alertSaving" @click="saveAlertRules">保存所有规则</a-button>
          </div>
        </a-card>
      </a-tab-pane>

      <!-- ── Tab 5: 审计日志（仅管理员）── -->
      <a-tab-pane v-if="isAdmin" key="audit" tab="审计日志">
        <a-card style="margin-bottom: 16px">
          <a-space wrap>
            <a-input
              v-model:value="auditFilter.user_id"
              placeholder="用户 ID"
              style="width: 120px"
              allow-clear
            />
            <a-select
              v-model:value="auditFilter.event_type"
              placeholder="事件类型"
              style="width: 180px"
              allow-clear
            >
              <a-select-option v-for="et in eventTypes" :key="et.value" :value="et.value">{{ et.label }}</a-select-option>
            </a-select>
            <a-range-picker
              v-model:value="auditDateRange"
              show-time
              format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DDTHH:mm:ss"
            />
            <a-button type="primary" @click="loadAuditLogs">查询</a-button>
            <a-button @click="handleExportAudit">导出 CSV</a-button>
          </a-space>
        </a-card>

        <a-table
          :columns="auditColumns"
          :data-source="auditLogs"
          :loading="auditLoading"
          row-key="id"
          :pagination="{
            total: auditTotal,
            pageSize: 50,
            current: auditPage,
            onChange: (p: number) => { auditPage.value = p; loadAuditLogs() }
          }"
          :expand-row-by-click="true"
        >
          <template #expandedRowRender="{ record }: { record: AuditLog }">
            <pre style="margin: 0; font-size: 12px; white-space: pre-wrap">{{ formatEventDetail(record.event_detail) }}</pre>
          </template>
          <template #bodyCell="{ column, record }: { column: { key: string }, record: AuditLog }">
            <template v-if="column.key === 'event_type'">
              <a-tag :color="eventTypeColor(record.event_type)">{{ record.event_type }}</a-tag>
            </template>
            <template v-else-if="column.key === 'result'">
              <a-badge
                :status="record.result === 'success' ? 'success' : 'error'"
                :text="record.result === 'success' ? '成功' : '失败'"
              />
            </template>
            <template v-else-if="column.key === 'event_time'">
              {{ record.event_time ? dayjs(record.event_time).format('YYYY-MM-DD HH:mm:ss') : '-' }}
            </template>
          </template>
        </a-table>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { getMyPreferences, updateMyPreferences, getMyDevices, updateMyDevice, deleteMyDevice } from '@/api/users'
import type { UserDevice } from '@/api/users'
import { getIPWhitelist, updateIPWhitelist, getMyIP, getAlertRules, updateAlertRules, testSNSAlert, getAuditLogs, exportAuditLogs } from '@/api/admin'
import type { AlertRule, AuditLog } from '@/api/admin'
import dayjs from 'dayjs'

const authStore = useAuthStore()
const { user, isAdmin } = storeToRefs(authStore)

const activeTab = ref('profile')

// ─── 偏好设置 ─────────────────────────────────────────────────────────────────
const prefSaving = ref(false)
const prefForm = reactive({ language: 'zh-CN', theme: 'light', timezone: 'Asia/Shanghai' })
const timezones = [
  'Asia/Shanghai', 'Asia/Tokyo', 'Asia/Seoul', 'Asia/Singapore',
  'America/New_York', 'America/Los_Angeles', 'America/Chicago',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'UTC',
]

async function savePref() {
  prefSaving.value = true
  try {
    await updateMyPreferences({ ...prefForm })
    message.success('设置已保存')
    await authStore.fetchCurrentUser()
  } finally {
    prefSaving.value = false
  }
}

// ─── 我的设备 ─────────────────────────────────────────────────────────────────
const devices = ref<UserDevice[]>([])
const devicesLoading = ref(false)
const editingDeviceId = ref<number | null>(null)
const editingDeviceName = ref('')

const deviceColumns = [
  { title: '设备名称', key: 'device_name' },
  { title: '指纹摘要', key: 'fingerprint_preview' },
  { title: '首次登录', dataIndex: 'first_seen_at', customRender: ({ text }: { text: string }) => text ? dayjs(text).format('YYYY-MM-DD HH:mm') : '-' },
  { title: '最后登录', dataIndex: 'last_seen_at', customRender: ({ text }: { text: string }) => text ? dayjs(text).format('YYYY-MM-DD HH:mm') : '-' },
  { title: '登录次数', dataIndex: 'login_count' },
  { title: '操作', key: 'actions' },
]

async function loadDevices() {
  devicesLoading.value = true
  try {
    const res = await getMyDevices()
    devices.value = res.data.data.devices
  } finally {
    devicesLoading.value = false
  }
}

function startEditDevice(record: UserDevice) {
  editingDeviceId.value = record.id
  editingDeviceName.value = record.device_name
}

function cancelEditDevice() {
  editingDeviceId.value = null
  editingDeviceName.value = ''
}

async function saveDeviceName(deviceId: number) {
  if (!editingDeviceName.value.trim()) return
  try {
    await updateMyDevice(deviceId, { device_name: editingDeviceName.value.trim() })
    message.success('设备名称已更新')
    cancelEditDevice()
    await loadDevices()
  } catch {
    // error handled by interceptor
  }
}

async function handleDeleteDevice(deviceId: number) {
  try {
    await deleteMyDevice(deviceId)
    message.success('设备已删除')
    await loadDevices()
  } catch {
    // error handled by interceptor
  }
}

// ─── IP 白名单 ─────────────────────────────────────────────────────────────────
interface WLEntry { key: number; cidr: string; note: string; cidrError: string }
const wlEnabled = ref(false)
const wlEntries = ref<WLEntry[]>([])
const wlSaving = ref(false)
const myIP = ref('')
const wlLockWarning = ref(false)
let wlEntryKey = 0

const cidrRegex = /^(\d{1,3}\.){3}\d{1,3}\/([0-9]|[1-2][0-9]|3[0-2])$|^([0-9a-fA-F:]+)\/([0-9]|[1-9][0-9]|1[0-1][0-9]|12[0-8])$/

const myIPInList = computed(() =>
  wlEntries.value.some(e => e.cidr === myIP.value || e.cidr === `${myIP.value}/32`)
)

const wlColumns = [
  { title: 'IP/CIDR 段', key: 'cidr', width: '40%' },
  { title: '备注说明', key: 'note' },
  { title: '操作', key: 'actions', width: 80 },
]

async function loadWhitelist() {
  try {
    const [wlRes, ipRes] = await Promise.all([getIPWhitelist(), getMyIP()])
    wlEnabled.value = wlRes.data.data.enabled
    wlEntries.value = wlRes.data.data.entries.map(e => ({
      key: wlEntryKey++,
      cidr: e.cidr,
      note: e.note || '',
      cidrError: '',
    }))
    myIP.value = ipRes.data.data.ip
  } catch {
    // error handled by interceptor
  }
}

function addWLEntry() {
  wlEntries.value.push({ key: wlEntryKey++, cidr: '', note: '', cidrError: '' })
}

function removeWLEntry(key: number) {
  wlEntries.value = wlEntries.value.filter(e => e.key !== key)
}

function addMyIPToList() {
  if (!myIPInList.value && myIP.value) {
    wlEntries.value.push({ key: wlEntryKey++, cidr: `${myIP.value}/32`, note: '我的当前 IP', cidrError: '' })
  }
}

function handleWLEnabledChange(val: boolean) {
  // 首次启用且列表为空时，自动预填当前 IP
  if (val && wlEntries.value.length === 0 && myIP.value) {
    addMyIPToList()
  }
}

function validateCIDR(entry: WLEntry) {
  if (!entry.cidr) { entry.cidrError = ''; return }
  entry.cidrError = cidrRegex.test(entry.cidr) ? '' : '格式错误，请输入有效的 IP/CIDR（如 203.0.113.0/24）'
}

function saveWhitelist() {
  // 校验所有 CIDR
  let hasError = false
  for (const e of wlEntries.value) {
    validateCIDR(e)
    if (e.cidrError || !e.cidr) hasError = true
  }
  if (hasError) { message.error('请修正 CIDR 格式错误后再保存'); return }

  // 若启用且当前 IP 不在列表中，弹出警告
  if (wlEnabled.value && myIP.value && !myIPInList.value) {
    wlLockWarning.value = true
    return
  }
  doSaveWhitelist()
}

async function doSaveWhitelist() {
  wlLockWarning.value = false
  wlSaving.value = true
  try {
    await updateIPWhitelist({
      enabled: wlEnabled.value,
      entries: wlEntries.value.map(e => ({ cidr: e.cidr, note: e.note })),
    })
    message.success('白名单已更新，Nginx 配置已重载')
  } finally {
    wlSaving.value = false
  }
}

// ─── 告警规则 ─────────────────────────────────────────────────────────────────
interface AlertRuleRow extends AlertRule {}
const alertRules = ref<AlertRuleRow[]>([])
const alertConfig = reactive({
  offhour_start: '22:00',
  offhour_end: '08:00',
  offhour_tz: 'Asia/Shanghai',
  cooldown_minutes: 30,
  sns_topic_arn: '',
})
const offhourStart = ref('22:00')
const offhourEnd = ref('08:00')
const alertSaving = ref(false)
const snsTesting = ref(false)

const alertRuleColumns = [
  { title: '规则名称', dataIndex: 'rule_name' },
  { title: '时间窗口', key: 'time_window_minutes' },
  { title: '触发阈值', key: 'threshold' },
  { title: '启用', key: 'enabled' },
]

async function loadAlertRules() {
  try {
    const res = await getAlertRules()
    alertRules.value = res.data.data.rules
    const cfg = res.data.data.config
    Object.assign(alertConfig, cfg)
    offhourStart.value = cfg.offhour_start
    offhourEnd.value = cfg.offhour_end
  } catch {
    // error handled by interceptor
  }
}

async function saveAlertRules() {
  alertSaving.value = true
  try {
    await updateAlertRules({
      rules: alertRules.value.map(r => ({
        rule_key: r.rule_key,
        time_window_minutes: r.time_window_minutes,
        threshold: r.threshold,
        enabled: r.enabled,
      })),
      config: {
        ...alertConfig,
        offhour_start: offhourStart.value,
        offhour_end: offhourEnd.value,
      },
    })
    message.success('告警规则已更新')
  } finally {
    alertSaving.value = false
  }
}

async function testSNS() {
  if (!alertConfig.sns_topic_arn) {
    message.warning('请先填写 SNS Topic ARN')
    return
  }
  snsTesting.value = true
  try {
    await testSNSAlert(alertConfig.sns_topic_arn)
    message.success('测试消息已发送，请检查 SNS 订阅')
  } catch {
    // error handled by interceptor
  } finally {
    snsTesting.value = false
  }
}

// ─── 审计日志 ─────────────────────────────────────────────────────────────────
const auditLogs = ref<AuditLog[]>([])
const auditLoading = ref(false)
const auditTotal = ref(0)
const auditPage = ref(1)
const auditDateRange = ref<[string, string] | null>(null)
const auditFilter = reactive<{ user_id: string; event_type: string }>({ user_id: '', event_type: '' })

const eventTypes = [
  { value: 'LOGIN', label: '登录' },
  { value: 'LOGOUT', label: '登出' },
  { value: 'SESSION_CREATE', label: '会话创建' },
  { value: 'SESSION_CLOSE', label: '会话关闭' },
  { value: 'TOKEN_VERIFY_FAIL', label: 'Token 验证失败' },
  { value: 'ADMIN_FORCE_LOGOUT', label: '强制下线' },
  { value: 'ADMIN_UPDATE_WHITELIST', label: '更新白名单' },
  { value: 'ADMIN_UPDATE_PERMISSIONS', label: '更新权限' },
  { value: 'NEW_DEVICE_LOGIN', label: '新设备登录' },
]

const auditColumns = [
  { title: '时间', key: 'event_time', width: 180 },
  { title: '用户', dataIndex: 'username' },
  { title: '事件类型', key: 'event_type' },
  { title: '客户端 IP', dataIndex: 'client_ip' },
  { title: '结果', key: 'result' },
]

function eventTypeColor(et: string): string {
  const map: Record<string, string> = {
    LOGIN: 'green', LOGOUT: 'default', SESSION_CREATE: 'blue', SESSION_CLOSE: 'default',
    TOKEN_VERIFY_FAIL: 'red', ADMIN_FORCE_LOGOUT: 'orange', NEW_DEVICE_LOGIN: 'purple',
  }
  return map[et] || 'default'
}

function formatEventDetail(detail: string | null): string {
  if (!detail) return ''
  try { return JSON.stringify(JSON.parse(detail), null, 2) } catch { return detail }
}

async function loadAuditLogs() {
  auditLoading.value = true
  try {
    const params: Record<string, unknown> = {
      limit: 50,
      offset: (auditPage.value - 1) * 50,
    }
    if (auditFilter.user_id) params.user_id = Number(auditFilter.user_id)
    if (auditFilter.event_type) params.event_type = auditFilter.event_type
    if (auditDateRange.value) {
      params.start_time = auditDateRange.value[0]
      params.end_time = auditDateRange.value[1]
    }
    const res = await getAuditLogs(params as Parameters<typeof getAuditLogs>[0])
    auditLogs.value = res.data.data.logs
    auditTotal.value = res.data.data.total
  } finally {
    auditLoading.value = false
  }
}

async function handleExportAudit() {
  try {
    const params: Record<string, unknown> = {}
    if (auditFilter.user_id) params.user_id = Number(auditFilter.user_id)
    if (auditFilter.event_type) params.event_type = auditFilter.event_type
    if (auditDateRange.value) {
      params.start_time = auditDateRange.value[0]
      params.end_time = auditDateRange.value[1]
    }
    const res = await exportAuditLogs(params as Parameters<typeof exportAuditLogs>[0])
    const url = URL.createObjectURL(new Blob([res.data as BlobPart]))
    const a = document.createElement('a')
    a.href = url
    a.download = `audit_logs_${dayjs().format('YYYYMMDD')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    message.error('导出失败')
  }
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────
onMounted(async () => {
  // 偏好设置
  try {
    const res = await getMyPreferences()
    Object.assign(prefForm, (res.data as { data: typeof prefForm }).data)
  } catch { /* use defaults */ }

  // 设备列表
  await loadDevices()

  // 管理员专属数据
  if (isAdmin.value) {
    await Promise.all([loadWhitelist(), loadAlertRules(), loadAuditLogs()])
  }
})
</script>

<style scoped>
:deep(.current-device-row) {
  background-color: #e6f4ff;
}
</style>
