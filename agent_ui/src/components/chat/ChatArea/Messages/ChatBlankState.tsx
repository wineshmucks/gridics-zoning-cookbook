'use client'

import { motion } from 'framer-motion'
import { useQueryState } from 'nuqs'
import { useMemo } from 'react'
import { toast } from 'sonner'
import useAIChatStreamHandler from '@/hooks/useAIStreamHandler'
import { useStore } from '@/store'

const DEFAULT_QUICK_QUESTIONS = [
  'Show me supported markets for TX',
  'Search parcels in a polygon in Denver, CO',
  'Run instant feasibility for 123 Main St, Austin, TX 78701'
]

const AGENT_QUICK_QUESTIONS: Record<string, string[]> = {
  'market-agent': [
    'What markets are currently supported in Texas?',
    'Is Florida available in the market list?',
    'List all supported markets in CA.'
  ],
  'search-agent': [
    'Find parcels in this polygon: [[-104.99,39.75],[-104.97,39.75],[-104.97,39.73],[-104.99,39.73],[-104.99,39.75]] for CO.',
    'Search parcels in this Miami polygon in FL: [[-80.20,25.79],[-80.18,25.79],[-80.18,25.77],[-80.20,25.77],[-80.20,25.79]].',
    'How many parcels are in this polygon near Phoenix, AZ?'
  ],
  'zoning-agent': [
    'Get the zoning record for 123 Biscayne Blvd, Miami, FL 33132.',
    'Check zoning details for 123 Biscayne Blvd, Miami, FL 33132.',
    'What are the key zoning constraints at 123 Biscayne Blvd, Miami, FL 33132?'
  ],
  'instant-feasibility-agent': [
    'Run instant feasibility for 123 Biscayne Blvd, Miami, FL 33132 with lot_size_sqft=8000 and proposed_use=multifamily.',
    'Can I build a duplex at 123 Biscayne Blvd, Miami, FL 33132?',
    'Feasibility check for ADU at 123 Biscayne Blvd, Miami, FL 33132.'
  ],
  'instant-availability-agent': [
    'Is zoning data available for 123 Main St, Austin, TX 78701?',
    'Check market availability for Miami, FL.',
    'Is parcel-level coverage available for Denver, CO?'
  ],
  'franchise-expansion-agent': [
    'Show me parcels where drive-thru restaurant is permitted and lot is > 25,000 SF.',
    'Build a zoning OK screen for quick-service restaurant: include parking, frontage, setbacks, and minimum lot size.',
  ]
}

const getQuickQuestions = (agentId: string | null | undefined): string[] => {
  if (!agentId) return DEFAULT_QUICK_QUESTIONS
  return AGENT_QUICK_QUESTIONS[agentId] ?? DEFAULT_QUICK_QUESTIONS
}

const ChatBlankState = () => {
  const { handleStreamResponse } = useAIChatStreamHandler()
  const [selectedAgent] = useQueryState('agent')
  const [selectedTeam] = useQueryState('team')
  const agents = useStore((state) => state.agents)
  const isStreaming = useStore((state) => state.isStreaming)

  const quickQuestions = useMemo(
    () => getQuickQuestions(selectedAgent),
    [selectedAgent]
  )
  const selectedAgentName = useMemo(() => {
    if (!selectedAgent) return null
    const match = agents.find((agent) => agent.id === selectedAgent)
    return match?.name ?? selectedAgent
  }, [agents, selectedAgent])

  const canSendQuestion = Boolean(selectedAgent || selectedTeam) && !isStreaming

  const handleQuickQuestion = async (question: string) => {
    if (!canSendQuestion) return
    try {
      await handleStreamResponse(question)
    } catch (error) {
      toast.error(
        `Error sending quick question: ${
          error instanceof Error ? error.message : String(error)
        }`
      )
    }
  }

  return (
    <section
      className="flex flex-col items-center text-center font-geist"
      aria-label="Welcome message"
    >
      <div className="flex max-w-3xl flex-col gap-y-6">
        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          className="text-3xl font-[600] tracking-tight"
        >
          <div className="flex items-center justify-center gap-x-2 font-medium">
            <span className="flex items-center font-[600]">Gridics Agent</span>
          </div>          
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.15 }}
          className="text-sm text-muted"
        >
          {selectedAgentName
            ? `Quick questions for ${selectedAgentName}`
            : 'Select an agent, then click a quick question to start.'}
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          className="grid gap-2"
        >
          {quickQuestions.map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => void handleQuickQuestion(question)}
              disabled={!canSendQuestion}
              className="rounded-xl border border-primary/15 bg-accent px-4 py-2 text-left text-xs font-medium text-primary transition hover:bg-accent/70 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {question}
            </button>
          ))}
        </motion.div>
      </div>
    </section>
  )
}

export default ChatBlankState
