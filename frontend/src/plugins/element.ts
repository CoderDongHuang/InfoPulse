import type { App } from 'vue'
import {
  ElButton, ElCheckbox, ElCheckboxGroup, ElDialog, ElDrawer,
  ElDropdown, ElDropdownItem, ElDropdownMenu, ElForm, ElFormItem,
  ElIcon, ElInput, ElOption, ElProgress, ElSelect, ElSlider,
  ElTabPane, ElTabs, ElTag, ElLoading,
} from 'element-plus'

// Official style modules include the components' internal dependencies.
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/checkbox/style/css'
import 'element-plus/es/components/checkbox-group/style/css'
import 'element-plus/es/components/dialog/style/css'
import 'element-plus/es/components/drawer/style/css'
import 'element-plus/es/components/dropdown/style/css'
import 'element-plus/es/components/dropdown-item/style/css'
import 'element-plus/es/components/dropdown-menu/style/css'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/icon/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/option/style/css'
import 'element-plus/es/components/progress/style/css'
import 'element-plus/es/components/select/style/css'
import 'element-plus/es/components/slider/style/css'
import 'element-plus/es/components/tab-pane/style/css'
import 'element-plus/es/components/tabs/style/css'
import 'element-plus/es/components/tag/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'

export const elementComponents = {
  ElButton, ElCheckbox, ElCheckboxGroup, ElDialog, ElDrawer,
  ElDropdown, ElDropdownItem, ElDropdownMenu, ElForm, ElFormItem,
  ElIcon, ElInput, ElOption, ElProgress, ElSelect, ElSlider,
  ElTabPane, ElTabs, ElTag,
}

export function installElement(app: App) {
  for (const [name, component] of Object.entries(elementComponents)) {
    app.component(name, component)
  }
  app.directive('loading', ElLoading.directive)
}
