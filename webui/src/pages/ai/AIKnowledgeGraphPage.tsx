import { useState, useEffect } from 'react'
import { Database, Search, Network, TrendingUp, Loader2 } from 'lucide-react'

interface Triple {
  id: number
  subject: string
  predicate: string
  object: string
  confidence: number
  timestamp: number
  source_chat_id: string
  context?: string
}

interface Entity {
  id: number
  name: string
  entity_type: string
  mention_count: number
  first_seen: number
  last_seen: number
}

interface Stats {
  triples: number
  entities: number
  relationships: number
  avg_confidence: number
  total_extractions?: number
  total_triples_extracted?: number
  avg_triples_per_extraction?: number
}

export default function AIKnowledgeGraphPage() {
  const [activeTab, setActiveTab] = useState<'stats' | 'triples' | 'entities' | 'query'>('stats')
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<Stats | null>(null)
  
  // Triples
  const [triples, setTriples] = useState<Triple[]>([])
  const [triplesTotal, setTriplesTotal] = useState(0)
  const [triplesPage, setTriplesPage] = useState(1)
  const [triplesFilter, setTriplesFilter] = useState({ subject: '', predicate: '', object: '' })
  
  // Entities
  const [entities, setEntities] = useState<Entity[]>([])
  const [entitiesTotal, setEntitiesTotal] = useState(0)
  const [entitiesPage, setEntitiesPage] = useState(1)
  const [entityTypeFilter, setEntityTypeFilter] = useState('')
  
  // Query
  const [queryText, setQueryText] = useState('')
  const [queryResults, setQueryResults] = useState<Triple[]>([])
  const [querying, setQuerying] = useState(false)
  
  const pageSize = 50

  useEffect(() => {
    loadStats()
  }, [])

  useEffect(() => {
    if (activeTab === 'triples') {
      loadTriples()
    } else if (activeTab === 'entities') {
      loadEntities()
    }
  }, [activeTab, triplesPage, entitiesPage, triplesFilter, entityTypeFilter])

  const loadStats = async () => {
    try {
      const response = await fetch('/api/ai/knowledge/stats')
      const data = await response.json()
      setStats(data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  const loadTriples = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        limit: pageSize.toString(),
        offset: ((triplesPage - 1) * pageSize).toString()
      })
      
      if (triplesFilter.subject) params.append('subject', triplesFilter.subject)
      if (triplesFilter.predicate) params.append('predicate', triplesFilter.predicate)
      if (triplesFilter.object) params.append('obj', triplesFilter.object)
      
      const response = await fetch(`/api/ai/knowledge/triples?${params}`)
      const data = await response.json()
      setTriples(data.items || [])
      setTriplesTotal(data.total || 0)
    } catch (error) {
      console.error('Failed to load triples:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadEntities = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        limit: pageSize.toString(),
        offset: ((entitiesPage - 1) * pageSize).toString()
      })
      
      if (entityTypeFilter) params.append('entity_type', entityTypeFilter)
      
      const response = await fetch(`/api/ai/knowledge/entities?${params}`)
      const data = await response.json()
      setEntities(data.items || [])
      setEntitiesTotal(data.total || 0)
    } catch (error) {
      console.error('Failed to load entities:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleQuery = async () => {
    if (!queryText.trim()) return
    
    setQuerying(true)
    try {
      const response = await fetch('/api/ai/knowledge/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryText, limit: 20 })
      })
      const data = await response.json()
      setQueryResults(data.results || [])
    } catch (error) {
      console.error('Failed to query knowledge:', error)
    } finally {
      setQuerying(false)
    }
  }

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN')
  }

  const renderPagination = (page: number, total: number, setPage: (p: number) => void) => {
    const totalPages = Math.ceil(total / pageSize)
    if (totalPages <= 1) return null

    return (
      <div className="flex items-center justify-between mt-4">
        <div className="text-sm text-gray-600">
          共 {total} 条记录，第 {page}/{totalPages} 页
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-3 py-1 border rounded disabled:opacity-50"
          >
            上一页
          </button>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-3 py-1 border rounded disabled:opacity-50"
          >
            下一页
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Network className="w-7 h-7" />
          知识图谱
        </h2>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <div className="flex space-x-4">
          {[
            { id: 'stats', label: '统计概览', icon: TrendingUp },
            { id: 'triples', label: '知识三元组', icon: Database },
            { id: 'entities', label: '实体列表', icon: Network },
            { id: 'query', label: '知识查询', icon: Search }
          ].map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`
                  flex items-center gap-2 px-4 py-2 border-b-2 transition-colors
                  ${activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                  }
                `}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Stats Tab */}
      {activeTab === 'stats' && stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg p-6 text-white">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm opacity-90">知识三元组</div>
              <Database className="w-5 h-5 opacity-75" />
            </div>
            <div className="text-3xl font-bold">{stats.triples}</div>
            {stats.total_triples_extracted !== undefined && (
              <div className="text-xs opacity-75 mt-1">
                总提取: {stats.total_triples_extracted}
              </div>
            )}
          </div>

          <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg p-6 text-white">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm opacity-90">实体数量</div>
              <Network className="w-5 h-5 opacity-75" />
            </div>
            <div className="text-3xl font-bold">{stats.entities}</div>
          </div>

          <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg p-6 text-white">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm opacity-90">关系类型</div>
              <Network className="w-5 h-5 opacity-75" />
            </div>
            <div className="text-3xl font-bold">{stats.relationships}</div>
          </div>

          <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-lg p-6 text-white">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm opacity-90">平均置信度</div>
              <TrendingUp className="w-5 h-5 opacity-75" />
            </div>
            <div className="text-3xl font-bold">{(stats.avg_confidence * 100).toFixed(1)}%</div>
          </div>

          {stats.total_extractions !== undefined && (
            <>
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <div className="text-sm text-gray-600 mb-2">总提取次数</div>
                <div className="text-2xl font-bold text-gray-900">{stats.total_extractions}</div>
              </div>

              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <div className="text-sm text-gray-600 mb-2">平均每次提取</div>
                <div className="text-2xl font-bold text-gray-900">
                  {stats.avg_triples_per_extraction?.toFixed(2) ?? '0'} 个三元组
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Triples Tab */}
      {activeTab === 'triples' && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <input
              type="text"
              placeholder="筛选主语..."
              value={triplesFilter.subject}
              onChange={(e) => {
                setTriplesFilter({ ...triplesFilter, subject: e.target.value })
                setTriplesPage(1)
              }}
              className="px-4 py-2 border rounded-lg"
            />
            <input
              type="text"
              placeholder="筛选谓语/关系..."
              value={triplesFilter.predicate}
              onChange={(e) => {
                setTriplesFilter({ ...triplesFilter, predicate: e.target.value })
                setTriplesPage(1)
              }}
              className="px-4 py-2 border rounded-lg"
            />
            <input
              type="text"
              placeholder="筛选宾语..."
              value={triplesFilter.object}
              onChange={(e) => {
                setTriplesFilter({ ...triplesFilter, object: e.target.value })
                setTriplesPage(1)
              }}
              className="px-4 py-2 border rounded-lg"
            />
          </div>

          {loading ? (
            <div className="text-center py-12">
              <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">主语</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">关系</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">宾语</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">置信度</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">来源</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {triples.map((triple) => (
                      <tr key={triple.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">{triple.subject}</td>
                        <td className="px-4 py-3 text-sm text-blue-600">{triple.predicate}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{triple.object}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {(triple.confidence * 100).toFixed(0)}%
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">{triple.source_chat_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{formatDate(triple.timestamp)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {renderPagination(triplesPage, triplesTotal, setTriplesPage)}
            </>
          )}
        </>
      )}

      {/* Entities Tab */}
      {activeTab === 'entities' && (
        <>
          <div className="mb-4">
            <input
              type="text"
              placeholder="筛选实体类型 (person/place/organization/thing/concept)..."
              value={entityTypeFilter}
              onChange={(e) => {
                setEntityTypeFilter(e.target.value)
                setEntitiesPage(1)
              }}
              className="px-4 py-2 border rounded-lg w-full max-w-md"
            />
          </div>

          {loading ? (
            <div className="text-center py-12">
              <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">实体名称</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">类型</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">提及次数</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">首次出现</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">最近出现</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {entities.map((entity) => (
                      <tr key={entity.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-medium text-gray-900">{entity.name}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700">
                            {entity.entity_type || 'unknown'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">{entity.mention_count}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{formatDate(entity.first_seen)}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{formatDate(entity.last_seen)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {renderPagination(entitiesPage, entitiesTotal, setEntitiesPage)}
            </>
          )}
        </>
      )}

      {/* Query Tab */}
      {activeTab === 'query' && (
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <Search className="w-5 h-5 text-blue-600 mt-0.5" />
              <div className="text-sm text-blue-800">
                使用自然语言查询知识图谱。例如："小明喜欢什么"、"告诉我关于北京的信息"
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              placeholder="输入自然语言查询..."
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
              className="flex-1 px-4 py-2 border rounded-lg"
            />
            <button
              onClick={handleQuery}
              disabled={querying || !queryText.trim()}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 flex items-center gap-2"
            >
              {querying ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  查询中...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  查询
                </>
              )}
            </button>
          </div>

          {queryResults.length > 0 && (
            <div className="space-y-4">
              <div className="text-sm text-gray-600">找到 {queryResults.length} 条相关知识</div>
              <div className="space-y-2">
                {queryResults.map((triple, idx) => (
                  <div key={idx} className="bg-white border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-medium text-gray-900">{triple.subject}</span>
                      <span className="text-blue-600">{triple.predicate}</span>
                      <span className="font-medium text-gray-900">{triple.object}</span>
                      <span className="ml-auto text-xs text-gray-500">
                        置信度: {(triple.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    {triple.context && (
                      <div className="mt-2 text-xs text-gray-600 bg-gray-50 p-2 rounded">
                        {triple.context}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

