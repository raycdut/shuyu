import React, { useMemo, useState } from 'react'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell,
} from 'recharts'

interface ChartRendererProps {
  columns: string[]
  data: any[][]
  title?: string
}

const COLORS = ['#4ca6a8', '#66c2cd', '#85d8ce', '#a3e9df', '#e8a87c', '#f4a2a2']

type ChartType = 'bar' | 'line' | 'pie'

function detectType(xKey: string, yKeys: string[], sampleRow: any[]): ChartType {
  if (yKeys.length === 1 && sampleRow.length <= 8) return 'pie'
  const xLower = xKey.toLowerCase()
  if (xLower.includes('date') || xLower.includes('time') || xLower.includes('年') || xLower.includes('月') || xLower.includes('日')) return 'line'
  return 'bar'
}

function isNumeric(val: any): boolean {
  return typeof val === 'number' && !Number.isNaN(val)
}

const ChartRenderer: React.FC<ChartRendererProps> = ({ columns, data, title }) => {
  const [chartType, setChartType] = useState<ChartType | null>(null)

  const chartConfig = useMemo(() => {
    if (columns.length < 2 || data.length === 0) return null
    const sampleRow = data[0]
    const numericIndices = sampleRow.map((v: any) => isNumeric(v))
    const numericCols: string[] = []
    columns.forEach((col, i) => {
      if (numericIndices[i]) numericCols.push(col)
    })
    if (numericCols.length === 0) return null
    const xAxisKey = columns.find((_, i) => !numericIndices[i]) || columns[0]
    const yAxisKeys = numericCols
    const detected = detectType(xAxisKey, yAxisKeys, columns)
    if (!chartType) setChartType(detected)
    return { xAxisKey, yAxisKeys, detected }
  }, [columns, data])

  const chartData = useMemo(() => {
    return data.map(row => {
      const obj: Record<string, any> = {}
      columns.forEach((col, i) => { obj[col] = row[i] })
      return obj
    })
  }, [columns, data])

  const type = chartType || chartConfig?.detected || 'bar'
  if (!chartConfig || data.length === 0) return null
  const { xAxisKey, yAxisKeys } = chartConfig

  const commonAxisProps = {
    fontSize: 10, tick: { fill: '#888' }, axisLine: { stroke: '#ddd' }
  }

  const renderChart = () => {
    if (type === 'pie') {
      return (
        <PieChart>
          <Pie
            data={chartData}
            dataKey={yAxisKeys[0]}
            nameKey={xAxisKey}
            cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}(${value})`}
          >
            {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip />
        </PieChart>
      )
    }
    if (type === 'line') {
      return (
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey={xAxisKey} {...commonAxisProps} />
          <YAxis {...commonAxisProps} />
          <Tooltip contentStyle={{ fontSize: '12px', borderRadius: '8px', border: '1px solid #eee' }} />
          <Legend wrapperStyle={{ fontSize: '10px' }} />
          {yAxisKeys.map((key, i) => (
            <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
          ))}
        </LineChart>
      )
    }
    return (
      <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={xAxisKey} {...commonAxisProps} />
        <YAxis {...commonAxisProps} />
        <Tooltip contentStyle={{ fontSize: '12px', borderRadius: '8px', border: '1px solid #eee' }} />
        <Legend wrapperStyle={{ fontSize: '10px' }} />
        {yAxisKeys.map((key, i) => (
          <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
        ))}
      </BarChart>
    )
  }

  const types: ChartType[] = ['bar', 'line', 'pie']

  return (
    <div className="w-full mt-3 mb-2 p-3 bg-white rounded-sm border border-tea/30 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        {title && <span className="text-xs font-medium text-ink-light">{title}</span>}
        <div className="flex items-center gap-1">
          {types.map(t => (
            <button
              key={t}
              onClick={() => setChartType(t)}
              className={`text-[10px] px-2 py-0.5 rounded-sm transition-colors ${
                type === t ? 'bg-celadon/10 text-celadon-dark font-medium' : 'text-ink-lighter hover:bg-smoke'
              }`}
            >
              {t === 'bar' ? '柱状图' : t === 'line' ? '折线图' : '饼图'}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        {renderChart()}
      </ResponsiveContainer>
    </div>
  )
}

export default ChartRenderer
