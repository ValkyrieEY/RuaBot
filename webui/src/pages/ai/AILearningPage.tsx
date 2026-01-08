import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Database, TrendingUp, MessageCircle, Users, Settings, Moon, GitBranch, Heart, Search, Loader2 } from 'lucide-react';

// Get axios instance with authentication
const getClient = () => {
  const token = localStorage.getItem('access_token');
  return axios.create({
    baseURL: '/api',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    }
  });
};

interface Expression {
  id: number;
  situation: string;
  style: string;
  chat_id: string;
  count: number;
  checked: boolean;
  rejected: boolean;
  created_at: string;
  updated_at: string;
}

interface Jargon {
  id: number;
  content: string;
  meaning: string | null;
  chat_id: string;
  count: number;
  is_jargon: boolean | null;
  is_complete: boolean;
  created_at: string;
  updated_at: string;
}

interface ChatHistory {
  id: number;
  chat_id: string;
  theme: string;
  summary: string;
  start_time: number;
  end_time: number;
  count: number;
  created_at: string;
}

interface MessageRecord {
  id: number;
  message_id: string;
  chat_id: string;
  plain_text: string;
  user_id: string;
  user_nickname: string;
  time: number;
  is_bot_message: boolean;
}

interface PersonInfo {
  id: number;
  person_id: string;
  person_name: string | null;
  nickname: string | null;
  is_known: boolean;
  memory_points: any;
  created_at: string;
}

interface GroupInfo {
  id: number;
  group_id: string;
  group_name: string | null;
  group_impression: string | null;
  topic: string | null;
  member_count: number;
  created_at: string;
}

interface Sticker {
  id: number;
  sticker_type: string;
  sticker_id: string | null;
  sticker_url: string | null;
  sticker_file: string | null;
  situation: string | null;
  emotion: string | null;
  meaning: string | null;
  chat_id: string;
  count: number;
  checked: boolean;
  rejected: boolean;
  created_at: string;
  last_active_time: number;
}

interface Stats {
  expressions_count: number;
  jargons_count: number;
  chat_history_count: number;
  message_records_count: number;
  persons_count: number;
  groups_count: number;
  known_persons_count: number;
  stickers_count: number;
}

const AILearningPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');
  const [clearingData, setClearingData] = useState(false);
  
  // Expressions
  const [expressions, setExpressions] = useState<Expression[]>([]);
  const [expressionsTotal, setExpressionsTotal] = useState(0);
  const [expressionsPage, setExpressionsPage] = useState(1);
  const [expressionsFilter, setExpressionsFilter] = useState('');
  
  // Jargons
  const [jargons, setJargons] = useState<Jargon[]>([]);
  const [jargonsTotal, setJargonsTotal] = useState(0);
  const [jargonsPage, setJargonsPage] = useState(1);
  const [jargonsFilter, setJargonsFilter] = useState('');
  
  // Chat History
  const [chatHistory, setChatHistory] = useState<ChatHistory[]>([]);
  const [chatHistoryTotal, setChatHistoryTotal] = useState(0);
  const [chatHistoryPage, setChatHistoryPage] = useState(1);
  const [chatHistoryFilter, setChatHistoryFilter] = useState('');
  
  // Message Records
  const [messageRecords, setMessageRecords] = useState<MessageRecord[]>([]);
  const [messageRecordsTotal, setMessageRecordsTotal] = useState(0);
  const [messageRecordsPage, setMessageRecordsPage] = useState(1);
  const [messageRecordsFilter, setMessageRecordsFilter] = useState('');
  
  // Persons
  const [persons, setPersons] = useState<PersonInfo[]>([]);
  const [personsTotal, setPersonsTotal] = useState(0);
  const [personsPage, setPersonsPage] = useState(1);
  
  // Groups
  const [groups, setGroups] = useState<GroupInfo[]>([]);
  const [groupsTotal, setGroupsTotal] = useState(0);
  const [groupsPage, setGroupsPage] = useState(1);

  // Stickers
  const [stickers, setStickers] = useState<Sticker[]>([]);
  const [stickersTotal, setStickersTotal] = useState(0);
  const [stickersPage, setStickersPage] = useState(1);
  const [stickersFilter, setStickersFilter] = useState('');
  
  // Learning Config
  const [learningConfig, setLearningConfig] = useState<any>(null);
  const [savingConfig, setSavingConfig] = useState(false);
  
  // Maintenance Stats
  const [maintenanceStats, setMaintenanceStats] = useState<any>({
    dream: null,
    check: null,
    reflect: null
  });
  
  // Knowledge Graph
  const [kgStats, setKgStats] = useState<any>(null);
  const [kgTriples, setKgTriples] = useState<any[]>([]);
  const [kgQueryText, setKgQueryText] = useState('');
  const [kgQueryResults, setKgQueryResults] = useState<any[]>([]);
  const [kgQuerying, setKgQuerying] = useState(false);
  const [kgActiveSubTab, setKgActiveSubTab] = useState<'triples' | 'query'>('triples');
  
  // HeartFlow
  const [heartflowChats, setHeartflowChats] = useState<any[]>([]);
  const [selectedHeartflowChat, setSelectedHeartflowChat] = useState<any>(null);

  const pageSize = 20;

  useEffect(() => {
    loadStats();
    loadLearningConfig();
  }, []);

  useEffect(() => {
    if (activeTab === 7) {
      loadMaintenanceStats();
      const interval = setInterval(loadMaintenanceStats, 30000); // 每30秒刷新
      return () => clearInterval(interval);
    } else if (activeTab === 8) {
      loadKnowledgeGraphData();
      const interval = setInterval(loadKnowledgeGraphData, 30000);
      return () => clearInterval(interval);
    } else if (activeTab === 9) {
      loadHeartflowData();
      const interval = setInterval(loadHeartflowData, 5000); // 每5秒刷新
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === 0) loadExpressions();
    else if (activeTab === 1) loadJargons();
    else if (activeTab === 2) loadChatHistory();
    else if (activeTab === 3) loadMessageRecords();
    else if (activeTab === 4) loadPersons();
    else if (activeTab === 5) loadGroups();
    else if (activeTab === 6) loadStickers();
    else if (activeTab === 7) loadMaintenanceStats();
    else if (activeTab === 8) loadKnowledgeGraphData();
    else if (activeTab === 9) loadHeartflowData();
    else if (activeTab === 10) loadLearningConfig();
  }, [activeTab, expressionsPage, expressionsFilter, jargonsPage, jargonsFilter, 
      chatHistoryPage, chatHistoryFilter, messageRecordsPage, messageRecordsFilter,
      personsPage, groupsPage, stickersPage, stickersFilter]);

  const loadStats = async () => {
    try {
      const response = await getClient().get('/ai/learning/stats');
      setStats(response.data);
    } catch (err: any) {
      console.error('Failed to load stats:', err);
    }
  };

  const loadExpressions = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (expressionsPage - 1) * pageSize,
      };
      if (expressionsFilter) params.chat_id = expressionsFilter;
      
      const response = await getClient().get('/ai/learning/expressions', { params });
      setExpressions(response.data.items);
      setExpressionsTotal(response.data.total);
      console.log(`[Expressions] Loaded ${response.data.items?.length || 0} expressions, total: ${response.data.total || 0}`);
    } catch (err: any) {
      console.error('Failed to load expressions:', err);
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadJargons = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (jargonsPage - 1) * pageSize,
      };
      if (jargonsFilter) params.chat_id = jargonsFilter;
      
      const response = await getClient().get('/ai/learning/jargons', { params });
      setJargons(response.data.items);
      setJargonsTotal(response.data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadChatHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (chatHistoryPage - 1) * pageSize,
      };
      if (chatHistoryFilter) params.chat_id = chatHistoryFilter;
      
      const response = await getClient().get('/ai/learning/chat-history', { params });
      setChatHistory(response.data.items || []);
      setChatHistoryTotal(response.data.total || 0);
      console.log(`[ChatHistory] Loaded ${response.data.items?.length || 0} items, total: ${response.data.total || 0}`);
    } catch (err: any) {
      console.error('Failed to load chat history:', err);
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadMessageRecords = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (messageRecordsPage - 1) * pageSize,
      };
      if (messageRecordsFilter) params.chat_id = messageRecordsFilter;
      
      const response = await getClient().get('/ai/learning/message-records', { params });
      setMessageRecords(response.data.items);
      setMessageRecordsTotal(response.data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadPersons = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (personsPage - 1) * pageSize,
      };
      
      const response = await getClient().get('/ai/learning/persons', { params });
      setPersons(response.data.items);
      setPersonsTotal(response.data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadGroups = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (groupsPage - 1) * pageSize,
      };
      
      const response = await getClient().get('/ai/learning/groups', { params });
      setGroups(response.data.items || []);
      setGroupsTotal(response.data.total || 0);
      console.log(`[Groups] Loaded ${response.data.items?.length || 0} groups, total: ${response.data.total || 0}`);
    } catch (err: any) {
      console.error('Failed to load groups:', err);
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadStickers = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {
        limit: pageSize,
        offset: (stickersPage - 1) * pageSize,
      };
      if (stickersFilter) params.chat_id = stickersFilter;
      
      const response = await getClient().get('/ai/learning/stickers', { params });
      setStickers(response.data.items);
      setStickersTotal(response.data.total);
      console.log(`[Stickers] Loaded ${response.data.items?.length || 0} stickers, total: ${response.data.total || 0}`);
    } catch (err: any) {
      console.error('Failed to load stickers:', err);
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('zh-CN');
  };

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN');
  };

  const loadLearningConfig = async () => {
    try {
      const response = await getClient().get('/ai/learning/config', {
        params: { config_type: 'global' }
      });
      setLearningConfig(response.data);
    } catch (error) {
      console.error('Failed to load learning config:', error);
      setError('加载配置失败');
    }
  };

  const saveLearningConfig = async () => {
    setSavingConfig(true);
    try {
      await getClient().put('/ai/learning/config', learningConfig, {
        params: { config_type: 'global' }
      });
      setError(null);
      alert('配置已保存');
    } catch (error) {
      console.error('Failed to save learning config:', error);
      setError('保存配置失败');
    } finally {
      setSavingConfig(false);
    }
  };

  const loadMaintenanceStats = async () => {
    try {
      const [dreamRes, checkRes, reflectRes] = await Promise.all([
        getClient().get('/ai/maintenance/dream/stats').catch((err) => {
          console.error('Failed to load dream stats:', err);
          return { data: null };
        }),
        getClient().get('/ai/maintenance/expression-check/stats').catch((err) => {
          console.error('Failed to load check stats:', err);
          return { data: null };
        }),
        getClient().get('/ai/maintenance/expression-reflect/stats').catch((err) => {
          console.error('Failed to load reflect stats:', err);
          return { data: null };
        })
      ]);
      setMaintenanceStats({
        dream: dreamRes.data,
        check: checkRes.data,
        reflect: reflectRes.data
      });
      console.log('[Maintenance] Stats loaded:', {
        dream: dreamRes.data ? '✓' : '✗',
        check: checkRes.data ? '✓' : '✗',
        reflect: reflectRes.data ? '✓' : '✗'
      });
    } catch (error) {
      console.error('Failed to load maintenance stats:', error);
    }
  };

  const loadKnowledgeGraphData = async () => {
    try {
      // Load stats
      const statsRes = await getClient().get('/ai/knowledge/stats').catch((err) => {
        console.error('Failed to load KG stats:', err);
        // Return default stats on error
        return { data: { triples: 0, entities: 0, relationships: 0, avg_confidence: 0.0 } };
      });
      setKgStats(statsRes.data || { triples: 0, entities: 0, relationships: 0, avg_confidence: 0.0 });
      
      // Load triples
      const triplesRes = await getClient().get('/ai/knowledge/triples', {
        params: { limit: 20, offset: 0 }
      }).catch((err) => {
        console.error('Failed to load KG triples:', err);
        // Return empty result on error
        return { data: { items: [], total: 0 } };
      });
      setKgTriples(triplesRes.data?.items || []);
      console.log(`[KG] Loaded ${triplesRes.data?.items?.length || 0} triples, total: ${triplesRes.data?.total || 0}`);
    } catch (error) {
      console.error('Failed to load knowledge graph data:', error);
      // Set default values on error
      setKgStats({ triples: 0, entities: 0, relationships: 0, avg_confidence: 0.0 });
      setKgTriples([]);
    }
  };

  const loadHeartflowData = async () => {
    try {
      const response = await getClient().get('/ai/heartflow/chats').catch((err) => {
        console.error('Failed to load heartflow chats:', err);
        return { data: { chats: [] } };
      });
      const chats = response.data?.chats || [];
      setHeartflowChats(chats);
      console.log(`[HeartFlow] Loaded ${chats.length} chats`, chats);
    } catch (error) {
      console.error('Failed to load heartflow data:', error);
      setHeartflowChats([]);
    }
  };

  const loadHeartflowChatDetails = async (chatId: string) => {
    try {
      const response = await getClient().get(`/ai/heartflow/stats/${encodeURIComponent(chatId)}`);
      setSelectedHeartflowChat({ chat_id: chatId, ...response.data });
    } catch (error) {
      console.error('Failed to load heartflow chat details:', error);
    }
  };

  const handleKgQuery = async () => {
    if (!kgQueryText.trim()) return;
    
    setKgQuerying(true);
    try {
      const response = await getClient().post('/ai/knowledge/query', {
        query: kgQueryText,
        limit: 20
      });
      setKgQueryResults(response.data.results || []);
      console.log(`[KG Query] Found ${response.data.results?.length || 0} results for: ${kgQueryText}`);
    } catch (error: any) {
      console.error('Failed to query knowledge:', error);
      setKgQueryResults([]);
      alert(error.response?.data?.detail || '查询失败，请重试');
    } finally {
      setKgQuerying(false);
    }
  };

  const handleClearAllData = async () => {
    if (confirmInput !== '确认格式化') {
      return;
    }

    setClearingData(true);
    try {
      const response = await getClient().delete('/ai/learning/clear-all');
      
      // Reset all data
      setExpressions([]);
      setExpressionsTotal(0);
      setJargons([]);
      setJargonsTotal(0);
      setChatHistory([]);
      setChatHistoryTotal(0);
      setMessageRecords([]);
      setMessageRecordsTotal(0);
      setPersons([]);
      setPersonsTotal(0);
      setGroups([]);
      setGroupsTotal(0);
      setStickers([]);
      setStickersTotal(0);
      
      // Reset new data
      setKgStats(null);
      setKgTriples([]);
      setHeartflowChats([]);
      setSelectedHeartflowChat(null);
      setMaintenanceStats({
        dream: null,
        check: null,
        reflect: null
      });
      
      // Reload stats
      await loadStats();
      
      // Reload current tab data if needed
      if (activeTab === 7) {
        await loadMaintenanceStats();
      } else if (activeTab === 8) {
        await loadKnowledgeGraphData();
      } else if (activeTab === 9) {
        await loadHeartflowData();
      }
      
      // Close dialog
      setShowConfirmDialog(false);
      setConfirmInput('');
      
      const clearedTables = response.data?.cleared_tables || [];
      alert(`所有学习数据已成功清除！\n\n已清除的表：\n${clearedTables.join('\n')}`);
    } catch (err: any) {
      console.error('Failed to clear data:', err);
      alert(err.response?.data?.detail || '清除失败，请重试');
    } finally {
      setClearingData(false);
    }
  };

  const renderPagination = (page: number, total: number, onChange: (page: number) => void) => {
    const totalPages = Math.ceil(total / pageSize);
    if (totalPages <= 1) return null;

    return (
      <div className="flex justify-center items-center mt-4 space-x-2">
        <button
          onClick={() => onChange(Math.max(1, page - 1))}
          disabled={page === 1}
          className="px-3 py-1 rounded border disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
        >
          上一页
        </button>
        <span className="px-4 py-1">
          第 {page} / {totalPages} 页 (共 {total} 条)
        </span>
        <button
          onClick={() => onChange(Math.min(totalPages, page + 1))}
          disabled={page === totalPages}
          className="px-3 py-1 rounded border disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
        >
          下一页
        </button>
      </div>
    );
  };

  return (
    <div className="p-6">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AI 学习数据</h1>
          <p className="text-gray-600 mt-2">查看 Xiaoyi_AI 的表达习惯、黑话、聊天历史、用户信息等学习数据</p>
        </div>
        <button
          onClick={() => setShowConfirmDialog(true)}
          className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
        >
          格式化数据
        </button>
      </div>

      {/* Confirm Dialog */}
      {showConfirmDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-bold text-gray-900 mb-4">确认格式化</h2>
            <p className="text-gray-600 mb-4">
              此操作将删除所有 AI 学习的数据，包括：
            </p>
            <ul className="list-disc list-inside text-gray-600 mb-4 space-y-1 text-sm">
              <li>表达习惯 (ai_expressions)</li>
              <li>黑话术语 (ai_jargons)</li>
              <li>表情包 (ai_stickers)</li>
              <li>聊天历史概要 (ai_chat_history)</li>
              <li>消息记录 (ai_message_records)</li>
              <li>用户画像 (ai_person_info)</li>
              <li>群组信息 (ai_group_info)</li>
              <li>表达使用追踪 (ai_expression_usage)</li>
              <li>知识图谱三元组 (kg_triples)</li>
              <li>知识图谱实体 (kg_entities)</li>
              <li>对话流状态 (HeartFlow)</li>
            </ul>
            <p className="text-red-600 font-semibold mb-4 text-sm">
              ⚠️ 警告：此操作不可恢复！所有学习到的数据将被永久删除。
            </p>
            <p className="text-gray-700 mb-4">
              请输入"<span className="font-mono font-bold">确认格式化</span>"以继续：
            </p>
            <input
              type="text"
              value={confirmInput}
              onChange={(e) => setConfirmInput(e.target.value)}
              placeholder="输入：确认格式化"
              className="w-full px-3 py-2 border border-gray-300 rounded mb-4 focus:outline-none focus:ring-2 focus:ring-red-500"
              disabled={clearingData}
            />
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  setShowConfirmDialog(false);
                  setConfirmInput('');
                }}
                className="flex-1 px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                disabled={clearingData}
              >
                取消
              </button>
              <button
                onClick={handleClearAllData}
                disabled={confirmInput !== '确认格式化' || clearingData}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {clearingData ? '清除中...' : '确认格式化'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">表达习惯</p>
                <p className="text-2xl font-bold text-gray-900">{stats.expressions_count}</p>
              </div>
              <TrendingUp className="w-8 h-8 text-blue-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">黑话术语</p>
                <p className="text-2xl font-bold text-gray-900">{stats.jargons_count}</p>
              </div>
              <Database className="w-8 h-8 text-green-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">消息记录</p>
                <p className="text-2xl font-bold text-gray-900">{stats.message_records_count}</p>
              </div>
              <MessageCircle className="w-8 h-8 text-purple-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">认识的人</p>
                <p className="text-2xl font-bold text-gray-900">
                  {stats.known_persons_count} / {stats.persons_count}
                </p>
              </div>
              <Users className="w-8 h-8 text-orange-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">表情包</p>
                <p className="text-2xl font-bold text-gray-900">{stats.stickers_count}</p>
              </div>
              <MessageCircle className="w-8 h-8 text-pink-500" />
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <div className="flex space-x-1 overflow-x-auto">
            {['表达习惯', '黑话术语', '聊天历史', '消息记录', '用户信息', '群组信息', '表情包', '自动维护', '知识图谱', '对话流', '功能配置'].map((label, index) => (
              <button
                key={index}
                onClick={() => setActiveTab(index)}
                className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === index
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-6">
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              {error}
            </div>
          )}

          {loading && (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
            </div>
          )}

          {/* Expressions Tab */}
          {activeTab === 0 && !loading && (
            <>
              <div className="mb-4">
                <input
                  type="text"
                  placeholder="筛选聊天 ID (例如: group:123456)"
                  value={expressionsFilter}
                  onChange={(e) => {
                    setExpressionsFilter(e.target.value);
                    setExpressionsPage(1);
                  }}
                  className="px-4 py-2 border rounded-lg w-full max-w-md"
                />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">情境</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">表达方式</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">来源</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">次数</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">状态</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">更新时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {expressions.map((expr) => (
                      <tr key={expr.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{expr.situation}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{expr.style}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{expr.chat_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{expr.count}</td>
                        <td className="px-4 py-3 text-sm">
                          {expr.rejected ? (
                            <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-700">已拒绝</span>
                          ) : expr.checked ? (
                            <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">已检查</span>
                          ) : (
                            <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-700">未检查</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">{formatDate(expr.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {renderPagination(expressionsPage, expressionsTotal, setExpressionsPage)}
            </>
          )}

          {/* Jargons Tab */}
          {activeTab === 1 && !loading && (
            <>
              <div className="mb-4">
                <input
                  type="text"
                  placeholder="筛选聊天 ID (例如: group:123456)"
                  value={jargonsFilter}
                  onChange={(e) => {
                    setJargonsFilter(e.target.value);
                    setJargonsPage(1);
                  }}
                  className="px-4 py-2 border rounded-lg w-full max-w-md"
                />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">黑话</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">推断含义</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">来源</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">次数</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">状态</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">更新时间</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {jargons.map((jargon) => (
                      <tr key={jargon.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{jargon.content}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{jargon.meaning || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{jargon.chat_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{jargon.count}</td>
                        <td className="px-4 py-3 text-sm">
                          {jargon.is_complete ? (
                            <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">已完成</span>
                          ) : jargon.is_jargon === true ? (
                            <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700">是黑话</span>
                          ) : jargon.is_jargon === false ? (
                            <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-700">非黑话</span>
                          ) : (
                            <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-700">待判定</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">{formatDate(jargon.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {renderPagination(jargonsPage, jargonsTotal, setJargonsPage)}
            </>
          )}

          {/* Similar patterns for other tabs... */}
          {activeTab === 2 && !loading && (
            <>
              <div className="mb-4">
                <input
                  type="text"
                  placeholder="筛选聊天 ID"
                  value={chatHistoryFilter}
                  onChange={(e) => {
                    setChatHistoryFilter(e.target.value);
                    setChatHistoryPage(1);
                  }}
                  className="px-4 py-2 border rounded-lg w-full max-w-md"
                />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">主题</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">概要</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">来源</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">检索次数</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {chatHistory.map((hist) => (
                      <tr key={hist.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{hist.theme}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{hist.summary.substring(0, 50)}...</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{hist.chat_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{hist.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {renderPagination(chatHistoryPage, chatHistoryTotal, setChatHistoryPage)}
            </>
          )}

          {/* Message Records */}
          {activeTab === 3 && !loading && (
            <>
              <div className="mb-4">
                <input
                  type="text"
                  placeholder="筛选聊天 ID"
                  value={messageRecordsFilter}
                  onChange={(e) => {
                    setMessageRecordsFilter(e.target.value);
                    setMessageRecordsPage(1);
                  }}
                  className="px-4 py-2 border rounded-lg w-full max-w-md"
                />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">内容</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">发送者</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">来源</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">时间</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">类型</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {messageRecords.map((record) => (
                      <tr key={record.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{record.plain_text?.substring(0, 50) || '-'}...</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{record.user_nickname || record.user_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{record.chat_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{formatTimestamp(record.time)}</td>
                        <td className="px-4 py-3 text-sm">
                          {record.is_bot_message ? (
                            <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700">机器人</span>
                          ) : (
                            <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-700">用户</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {renderPagination(messageRecordsPage, messageRecordsTotal, setMessageRecordsPage)}
            </>
          )}

          {/* Persons */}
          {activeTab === 4 && !loading && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">用户 ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">AI 记住的名字</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">昵称</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">状态</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {persons.map((person) => (
                      <tr key={person.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{person.person_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{person.person_name || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{person.nickname || '-'}</td>
                        <td className="px-4 py-3 text-sm">
                          {person.is_known ? (
                            <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">已认识</span>
                          ) : (
                            <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-700">未认识</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {renderPagination(personsPage, personsTotal, setPersonsPage)}
            </>
          )}

          {/* Groups */}
          {activeTab === 5 && !loading && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">群 ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">群名称</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">群印象</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">成员数</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {groups.map((group) => (
                      <tr key={group.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{group.group_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{group.group_name || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{group.group_impression?.substring(0, 30) || '-'}...</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{group.member_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {renderPagination(groupsPage, groupsTotal, setGroupsPage)}
            </>
          )}

          {/* Stickers */}
          {activeTab === 6 && !loading && (
            <>
              <div className="mb-4">
                <input
                  type="text"
                  placeholder="筛选聊天 ID (例如: group:123456)"
                  value={stickersFilter}
                  onChange={(e) => {
                    setStickersFilter(e.target.value);
                    setStickersPage(1);
                  }}
                  className="px-4 py-2 border rounded-lg w-full max-w-md"
                />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">类型</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">情境</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">情感</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">含义</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">来源</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">使用次数</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">状态</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">最后使用</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {stickers.map((sticker) => (
                      <tr key={sticker.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{sticker.sticker_type}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{sticker.situation || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{sticker.emotion || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-600" title={sticker.meaning || ''}>
                          {sticker.meaning ? sticker.meaning.substring(0, 30) + '...' : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">{sticker.chat_id}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{sticker.count}</td>
                        <td className="px-4 py-3 text-sm">
                          {sticker.rejected ? (
                            <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-700">已拒绝</span>
                          ) : sticker.checked ? (
                            <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-700">已检查</span>
                          ) : (
                            <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-700">未检查</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {sticker.last_active_time ? formatTimestamp(sticker.last_active_time) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {renderPagination(stickersPage, stickersTotal, setStickersPage)}
            </>
          )}

          {/* Maintenance Tab */}
          {activeTab === 7 && (
            <div className="space-y-6">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start gap-2">
                  <Settings className="w-5 h-5 text-blue-600 mt-0.5" />
                  <div className="text-sm text-blue-800">
                    <div className="font-medium mb-1">AI 自动维护系统</div>
                    <div>包括梦境系统（自动整理记忆）、表达方式自动检查、表达方式反思等功能</div>
                  </div>
                </div>
              </div>

              {/* Dream System Stats */}
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-4">
                  <Moon className="w-5 h-5 text-blue-600" />
                  <h3 className="text-lg font-semibold">Dream 梦境维护系统</h3>
                </div>
                {maintenanceStats.dream ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">总周期数</div>
                      <div className="text-xl font-bold text-gray-900">{maintenanceStats.dream.total_cycles || 0}</div>
                    </div>
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">成功率</div>
                      <div className="text-xl font-bold text-green-600">
                        {maintenanceStats.dream.total_cycles > 0
                          ? `${((maintenanceStats.dream.successful_cycles || 0) / maintenanceStats.dream.total_cycles * 100).toFixed(1)}%`
                          : '0%'}
                      </div>
                    </div>
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">总迭代数</div>
                      <div className="text-xl font-bold text-gray-900">{maintenanceStats.dream.total_iterations || 0}</div>
                    </div>
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">运行状态</div>
                      <div className="text-xl font-bold">
                        {maintenanceStats.dream.is_running ? (
                          <span className="text-green-600">运行中</span>
                        ) : (
                          <span className="text-gray-500">已停止</span>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-4 text-gray-500">暂无数据</div>
                )}
              </div>

              {/* Expression Check Stats */}
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-4">
                  <Settings className="w-5 h-5 text-green-600" />
                  <h3 className="text-lg font-semibold">表达方式自动检查</h3>
                </div>
                {maintenanceStats.check ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">已检查</div>
                      <div className="text-xl font-bold text-gray-900">{maintenanceStats.check.total_checked || 0}</div>
                    </div>
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">已接受</div>
                      <div className="text-xl font-bold text-green-600">{maintenanceStats.check.total_accepted || 0}</div>
                    </div>
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">已拒绝</div>
                      <div className="text-xl font-bold text-red-600">{maintenanceStats.check.total_rejected || 0}</div>
                    </div>
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">接受率</div>
                      <div className="text-xl font-bold text-blue-600">
                        {maintenanceStats.check.total_checked > 0
                          ? `${((maintenanceStats.check.total_accepted || 0) / maintenanceStats.check.total_checked * 100).toFixed(1)}%`
                          : '0%'}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-4 text-gray-500">暂无数据</div>
                )}
              </div>

              {/* Expression Reflect Stats */}
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-4">
                  <Settings className="w-5 h-5 text-purple-600" />
                  <h3 className="text-lg font-semibold">表达方式反思</h3>
                </div>
                {maintenanceStats.reflect ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">总反思次数</div>
                      <div className="text-xl font-bold text-gray-900">{maintenanceStats.reflect.total_reflections || 0}</div>
                    </div>
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">已分析</div>
                      <div className="text-xl font-bold text-blue-600">{maintenanceStats.reflect.total_analyzed || 0}</div>
                    </div>
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">建议数</div>
                      <div className="text-xl font-bold text-purple-600">{maintenanceStats.reflect.total_recommendations || 0}</div>
                    </div>
                    <div className="bg-white border rounded-lg p-3">
                      <div className="text-xs text-gray-600">追踪表达</div>
                      <div className="text-xl font-bold text-gray-900">{maintenanceStats.reflect.tracked_expressions || 0}</div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-4 text-gray-500">暂无数据</div>
                )}
              </div>
            </div>
          )}

          {/* Knowledge Graph Tab */}
          {activeTab === 8 && (
            <div className="space-y-6">
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <div className="flex items-start gap-2">
                  <GitBranch className="w-5 h-5 text-purple-600 mt-0.5" />
                  <div className="text-sm text-purple-800">
                    <div className="font-medium mb-1">知识图谱系统</div>
                    <div>从对话中自动提取知识三元组，构建实体关系网络</div>
                  </div>
                </div>
              </div>

              {/* Stats */}
              {kgStats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg p-4 text-white">
                    <div className="text-sm opacity-90">知识三元组</div>
                    <div className="text-2xl font-bold">{kgStats.triples || 0}</div>
                  </div>
                  <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg p-4 text-white">
                    <div className="text-sm opacity-90">实体数量</div>
                    <div className="text-2xl font-bold">{kgStats.entities || 0}</div>
                  </div>
                  <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg p-4 text-white">
                    <div className="text-sm opacity-90">关系类型</div>
                    <div className="text-2xl font-bold">{kgStats.relationships || 0}</div>
                  </div>
                  <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-lg p-4 text-white">
                    <div className="text-sm opacity-90">平均置信度</div>
                    <div className="text-2xl font-bold">
                      {kgStats.avg_confidence ? `${(kgStats.avg_confidence * 100).toFixed(1)}%` : '0%'}
                    </div>
                  </div>
                </div>
              )}

              {/* Sub Tabs */}
              <div className="border-b border-gray-200">
                <div className="flex space-x-4">
                  {[
                    { id: 'triples', label: '知识三元组', icon: Database },
                    { id: 'query', label: '自然语言查询', icon: Search }
                  ].map((tab) => {
                    const Icon = tab.icon;
                    return (
                      <button
                        key={tab.id}
                        onClick={() => setKgActiveSubTab(tab.id as any)}
                        className={`
                          flex items-center gap-2 px-4 py-2 border-b-2 transition-colors
                          ${kgActiveSubTab === tab.id
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-600 hover:text-gray-900'
                          }
                        `}
                      >
                        <Icon className="w-4 h-4" />
                        {tab.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Triples Sub Tab */}
              {kgActiveSubTab === 'triples' && (
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold">最近提取的知识三元组</h3>
                  <button
                    onClick={loadKnowledgeGraphData}
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    刷新
                  </button>
                </div>
                {kgTriples.length > 0 ? (
                  <div className="space-y-2">
                    {kgTriples.slice(0, 10).map((triple: any, idx: number) => (
                      <div key={idx} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                        <div className="flex items-center gap-2 text-sm">
                          <span className="font-medium text-gray-900">{triple.subject}</span>
                          <span className="text-blue-600">{triple.predicate}</span>
                          <span className="font-medium text-gray-900">{triple.object}</span>
                          <span className="ml-auto text-xs text-gray-500">
                            置信度: {(triple.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        {triple.context && (
                          <div className="mt-2 text-xs text-gray-600 bg-white p-2 rounded">
                            {triple.context.substring(0, 100)}...
                          </div>
                        )}
                        <div className="mt-1 text-xs text-gray-400">
                          来源: {triple.source_chat_id} | {new Date(triple.timestamp * 1000).toLocaleString('zh-CN')}
                        </div>
                      </div>
                    ))}
                    {kgTriples.length >= 10 && (
                      <div className="text-center text-sm text-gray-500 mt-2">
                        显示最近 10 条，共 {kgStats?.triples || 0} 条三元组
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    {kgStats?.triples === 0 ? (
                      <div>
                        <p>暂无知识三元组</p>
                        <p className="text-xs mt-2">系统正在从对话中提取知识，请稍候...</p>
                      </div>
                    ) : (
                      <div>
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
                        加载中...
                      </div>
                    )}
                  </div>
                )}
              </div>
              )}

              {/* Query Sub Tab */}
              {kgActiveSubTab === 'query' && (
                <div className="space-y-4">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <div className="flex items-start gap-2">
                      <Search className="w-5 h-5 text-blue-600 mt-0.5" />
                      <div className="text-sm text-blue-800">
                        <div className="font-medium mb-1">自然语言知识查询</div>
                        <div>使用自然语言查询知识图谱。例如："小明喜欢什么"、"告诉我关于北京的信息"</div>
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="输入自然语言查询..."
                      value={kgQueryText}
                      onChange={(e) => setKgQueryText(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleKgQuery()}
                      className="flex-1 px-4 py-2 border rounded-lg"
                    />
                    <button
                      onClick={handleKgQuery}
                      disabled={kgQuerying || !kgQueryText.trim()}
                      className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 flex items-center gap-2"
                    >
                      {kgQuerying ? (
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

                  {kgQueryResults.length > 0 && (
                    <div className="space-y-4">
                      <div className="text-sm text-gray-600">找到 {kgQueryResults.length} 条相关知识</div>
                      <div className="space-y-2">
                        {kgQueryResults.map((triple: any, idx: number) => (
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
                            {triple.source_chat_id && (
                              <div className="mt-1 text-xs text-gray-400">
                                来源: {triple.source_chat_id} | {triple.timestamp ? new Date(triple.timestamp * 1000).toLocaleString('zh-CN') : ''}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {kgQueryResults.length === 0 && kgQueryText && !kgQuerying && (
                    <div className="text-center py-8 text-gray-500">
                      <p>未找到相关结果</p>
                      <p className="text-xs mt-2">尝试使用不同的关键词或更具体的查询</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* HeartFlow Tab */}
          {activeTab === 9 && (
            <div className="space-y-6">
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start gap-2">
                  <Heart className="w-5 h-5 text-red-600 mt-0.5" />
                  <div className="text-sm text-red-800">
                    <div className="font-medium mb-1">HeartFlow 脑流系统</div>
                    <div>智能监控对话氛围、情感状态、参与度，动态调节回复策略</div>
                  </div>
                </div>
              </div>

              {/* Overview Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg p-4 text-white">
                  <div className="text-sm opacity-90">活跃对话</div>
                  <div className="text-2xl font-bold">{heartflowChats.length}</div>
                </div>
                <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-lg p-4 text-white">
                  <div className="text-sm opacity-90">总消息数</div>
                  <div className="text-2xl font-bold">
                    {heartflowChats.reduce((sum, chat) => sum + (chat.message_count || 0), 0)}
                  </div>
                </div>
                <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg p-4 text-white">
                  <div className="text-sm opacity-90">总回复数</div>
                  <div className="text-2xl font-bold">
                    {heartflowChats.reduce((sum, chat) => sum + (chat.reply_count || 0), 0)}
                  </div>
                </div>
                <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-lg p-4 text-white">
                  <div className="text-sm opacity-90">平均回复率</div>
                  <div className="text-2xl font-bold">
                    {heartflowChats.length > 0
                      ? (heartflowChats.reduce((sum, chat) => sum + (chat.reply_ratio || 0), 0) / heartflowChats.length * 100).toFixed(1)
                      : 0}%
                  </div>
                </div>
              </div>

              {/* Chat List */}
              <div className="border border-gray-200 rounded-lg">
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                  <h3 className="text-lg font-semibold">对话列表</h3>
                </div>
                <div className="divide-y divide-gray-200">
                  {heartflowChats.length === 0 ? (
                    <div className="px-6 py-12 text-center text-gray-500">暂无活跃对话</div>
                  ) : (
                    heartflowChats.map((chat: any) => (
                      <div
                        key={chat.chat_id}
                        className="px-6 py-4 hover:bg-gray-50 cursor-pointer transition-colors"
                        onClick={() => loadHeartflowChatDetails(chat.chat_id)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="font-medium text-gray-900">{chat.chat_id}</div>
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-1 text-xs rounded-full ${
                              chat.atmosphere === 'silent' ? 'bg-gray-100 text-gray-700' :
                              chat.atmosphere === 'calm' ? 'bg-blue-100 text-blue-700' :
                              chat.atmosphere === 'active' ? 'bg-green-100 text-green-700' :
                              chat.atmosphere === 'heated' ? 'bg-orange-100 text-orange-700' :
                              'bg-red-100 text-red-700'
                            }`}>
                              {chat.atmosphere === 'silent' ? '沉默' :
                               chat.atmosphere === 'calm' ? '平静' :
                               chat.atmosphere === 'active' ? '活跃' :
                               chat.atmosphere === 'heated' ? '热烈' : '混乱'}
                            </span>
                            <span className="text-2xl">
                              {chat.emotional_state === 'neutral' ? '😐' :
                               chat.emotional_state === 'happy' ? '😊' :
                               chat.emotional_state === 'excited' ? '🤩' :
                               chat.emotional_state === 'sad' ? '😢' :
                               chat.emotional_state === 'angry' ? '😠' :
                               chat.emotional_state === 'confused' ? '😕' : '🤔'}
                            </span>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-600">
                          <div>
                            <div className="text-xs text-gray-500">活跃参与者</div>
                            <div className="font-medium">{chat.active_participants || 0}</div>
                          </div>
                          <div>
                            <div className="text-xs text-gray-500">消息数</div>
                            <div className="font-medium">{chat.message_count || 0}</div>
                          </div>
                          <div>
                            <div className="text-xs text-gray-500">回复率</div>
                            <div className="font-medium">{((chat.reply_ratio || 0) * 100).toFixed(1)}%</div>
                          </div>
                          <div>
                            <div className="text-xs text-gray-500">话题活跃度</div>
                            <div className="font-medium">{((chat.topic_activity || 0) * 100).toFixed(0)}%</div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Selected Chat Details */}
              {selectedHeartflowChat && (
                <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold">对话详情: {selectedHeartflowChat.chat_id}</h3>
                    <button
                      onClick={() => setSelectedHeartflowChat(null)}
                      className="text-gray-500 hover:text-gray-700 text-sm"
                    >
                      关闭
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm font-medium text-gray-700 mb-2">对话氛围</div>
                      <div className="text-lg font-medium">
                        {selectedHeartflowChat.atmosphere === 'silent' ? '沉默' :
                         selectedHeartflowChat.atmosphere === 'calm' ? '平静' :
                         selectedHeartflowChat.atmosphere === 'active' ? '活跃' :
                         selectedHeartflowChat.atmosphere === 'heated' ? '热烈' : '混乱'}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-700 mb-2">情感状态</div>
                      <div className="text-lg font-medium">
                        {selectedHeartflowChat.emotional_state === 'neutral' ? '中立' :
                         selectedHeartflowChat.emotional_state === 'happy' ? '开心' :
                         selectedHeartflowChat.emotional_state === 'excited' ? '兴奋' :
                         selectedHeartflowChat.emotional_state === 'sad' ? '悲伤' :
                         selectedHeartflowChat.emotional_state === 'angry' ? '愤怒' :
                         selectedHeartflowChat.emotional_state === 'confused' ? '困惑' : '思考'}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Learning Config Tab */}
          {activeTab === 10 && (
            <div className="space-y-6">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start gap-2">
                  <Settings className="w-5 h-5 text-blue-600 mt-0.5" />
                  <div className="text-sm text-blue-800">
                    <div className="font-medium mb-1">学习功能配置</div>
                    <div>配置各个学习功能的启用状态和参数</div>
                  </div>
                </div>
              </div>

              {learningConfig ? (
                <div className="space-y-6">
                  {/* Expression Learning */}
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold">表达方式学习</h3>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={learningConfig.expression_learning?.enabled ?? true}
                          onChange={(e) => {
                            setLearningConfig({
                              ...learningConfig,
                              expression_learning: {
                                ...learningConfig.expression_learning,
                                enabled: e.target.checked
                              }
                            });
                          }}
                          className="w-4 h-4"
                        />
                        <span className="text-sm">启用</span>
                      </label>
                    </div>
                    {learningConfig.expression_learning?.enabled && (
                      <div className="space-y-3 ml-6">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={learningConfig.expression_learning?.use_expressions ?? true}
                            onChange={(e) => {
                              setLearningConfig({
                                ...learningConfig,
                                expression_learning: {
                                  ...learningConfig.expression_learning,
                                  use_expressions: e.target.checked
                                }
                              });
                            }}
                            className="w-4 h-4"
                          />
                          <span className="text-sm">在回复中使用学到的表达方式</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={learningConfig.expression_learning?.auto_check ?? true}
                            onChange={(e) => {
                              setLearningConfig({
                                ...learningConfig,
                                expression_learning: {
                                  ...learningConfig.expression_learning,
                                  auto_check: e.target.checked
                                }
                              });
                            }}
                            className="w-4 h-4"
                          />
                          <span className="text-sm">自动检查表达质量</span>
                        </label>
                      </div>
                    )}
                  </div>

                  {/* Jargon Learning */}
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold">黑话术语学习</h3>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={learningConfig.jargon_learning?.enabled ?? true}
                          onChange={(e) => {
                            setLearningConfig({
                              ...learningConfig,
                              jargon_learning: {
                                ...learningConfig.jargon_learning,
                                enabled: e.target.checked
                              }
                            });
                          }}
                          className="w-4 h-4"
                        />
                        <span className="text-sm">启用</span>
                      </label>
                    </div>
                    {learningConfig.jargon_learning?.enabled && (
                      <div className="ml-6">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={learningConfig.jargon_learning?.explain_jargons ?? true}
                            onChange={(e) => {
                              setLearningConfig({
                                ...learningConfig,
                                jargon_learning: {
                                  ...learningConfig.jargon_learning,
                                  explain_jargons: e.target.checked
                                }
                              });
                            }}
                            className="w-4 h-4"
                          />
                          <span className="text-sm">在回复中解释黑话</span>
                        </label>
                      </div>
                    )}
                  </div>

                  {/* Sticker Learning */}
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold">表情包学习</h3>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={learningConfig.sticker_learning?.enabled ?? true}
                          onChange={(e) => {
                            setLearningConfig({
                              ...learningConfig,
                              sticker_learning: {
                                ...learningConfig.sticker_learning,
                                enabled: e.target.checked
                              }
                            });
                          }}
                          className="w-4 h-4"
                        />
                        <span className="text-sm">启用</span>
                      </label>
                    </div>
                    {learningConfig.sticker_learning?.enabled && (
                      <div className="ml-6">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={learningConfig.sticker_learning?.use_stickers ?? true}
                            onChange={(e) => {
                              setLearningConfig({
                                ...learningConfig,
                                sticker_learning: {
                                  ...learningConfig.sticker_learning,
                                  use_stickers: e.target.checked
                                }
                              });
                            }}
                            className="w-4 h-4"
                          />
                          <span className="text-sm">在回复中使用学到的表情包</span>
                        </label>
                      </div>
                    )}
                  </div>

                  {/* Knowledge Graph */}
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold">知识图谱</h3>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={learningConfig.knowledge_graph?.enabled ?? true}
                          onChange={(e) => {
                            setLearningConfig({
                              ...learningConfig,
                              knowledge_graph: {
                                ...learningConfig.knowledge_graph,
                                enabled: e.target.checked
                              }
                            });
                          }}
                          className="w-4 h-4"
                        />
                        <span className="text-sm">启用</span>
                      </label>
                    </div>
                    {learningConfig.knowledge_graph?.enabled && (
                      <div className="space-y-3 ml-6">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={learningConfig.knowledge_graph?.extract_triples ?? true}
                            onChange={(e) => {
                              setLearningConfig({
                                ...learningConfig,
                                knowledge_graph: {
                                  ...learningConfig.knowledge_graph,
                                  extract_triples: e.target.checked
                                }
                              });
                            }}
                            className="w-4 h-4"
                          />
                          <span className="text-sm">提取知识三元组</span>
                        </label>
                        <div>
                          <label className="text-sm text-gray-700">
                            每条消息最大提取三元组数
                          </label>
                          <input
                            type="number"
                            min="1"
                            max="20"
                            value={learningConfig.knowledge_graph?.max_triples_per_message ?? 5}
                            onChange={(e) => {
                              setLearningConfig({
                                ...learningConfig,
                                knowledge_graph: {
                                  ...learningConfig.knowledge_graph,
                                  max_triples_per_message: parseInt(e.target.value) || 5
                                }
                              });
                            }}
                            className="mt-1 px-3 py-2 border rounded-lg w-32"
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* HeartFlow */}
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold">HeartFlow 对话流</h3>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={learningConfig.heartflow?.enabled ?? true}
                          onChange={(e) => {
                            setLearningConfig({
                              ...learningConfig,
                              heartflow: {
                                ...learningConfig.heartflow,
                                enabled: e.target.checked
                              }
                            });
                          }}
                          className="w-4 h-4"
                        />
                        <span className="text-sm">启用</span>
                      </label>
                    </div>
                    {learningConfig.heartflow?.enabled && (
                      <div className="space-y-3 ml-6">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={learningConfig.heartflow?.track_emotions ?? true}
                            onChange={(e) => {
                              setLearningConfig({
                                ...learningConfig,
                                heartflow: {
                                  ...learningConfig.heartflow,
                                  track_emotions: e.target.checked
                                }
                              });
                            }}
                            className="w-4 h-4"
                          />
                          <span className="text-sm">追踪情感状态</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={learningConfig.heartflow?.track_atmosphere ?? true}
                            onChange={(e) => {
                              setLearningConfig({
                                ...learningConfig,
                                heartflow: {
                                  ...learningConfig.heartflow,
                                  track_atmosphere: e.target.checked
                                }
                              });
                            }}
                            className="w-4 h-4"
                          />
                          <span className="text-sm">追踪对话氛围</span>
                        </label>
                      </div>
                    )}
                  </div>

                  {/* Save Button */}
                  <div className="flex justify-end">
                    <button
                      onClick={saveLearningConfig}
                      disabled={savingConfig}
                      className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 flex items-center gap-2"
                    >
                      {savingConfig ? '保存中...' : '保存配置'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  加载配置中...
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AILearningPage;
