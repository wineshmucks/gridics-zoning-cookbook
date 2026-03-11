'use client'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select'
import { MARKET_AREA_OPTIONS } from '@/lib/marketAreas'
import { useStore } from '@/store'
import { useQueryState } from 'nuqs'

export function MarketAreaSelector() {
  const selectedMarketArea = useStore((state) => state.selectedMarketArea)
  const setSelectedMarketArea = useStore((state) => state.setSelectedMarketArea)
  const setMessages = useStore((state) => state.setMessages)
  const [, setSessionId] = useQueryState('session')

  const onChange = (value: string) => {
    setSelectedMarketArea(value)
    setMessages([])
    setSessionId(null)
  }

  return (
    <div className="flex w-full flex-col items-start gap-2">
      <div className="text-xs font-medium uppercase text-primary">
        Market Area
      </div>
      <Select value={selectedMarketArea} onValueChange={onChange}>
        <SelectTrigger className="h-9 w-full rounded-xl border border-primary/15 bg-primaryAccent text-xs font-medium uppercase">
          <SelectValue placeholder="Auto (Use Prompt)" />
        </SelectTrigger>
        <SelectContent className="border-none bg-primaryAccent font-dmmono shadow-lg">
          {MARKET_AREA_OPTIONS.map((option) => (
            <SelectItem
              key={option.label}
              value={option.value}
              className="cursor-pointer"
            >
              <div className="text-xs font-medium uppercase">{option.label}</div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
