import { useOutletContext } from 'react-router'

import type { ShellContext } from '../components/shell/AppShell'

export function useShell(): ShellContext {
  return useOutletContext<ShellContext>()
}
