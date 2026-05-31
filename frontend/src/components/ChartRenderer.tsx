import React, { useMemo } from 'react'
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell
} from 'recharts'

interface ChartRendererProps {
  columns: string[]
  data: any[][]
  title?: string
}

/**
 * 图表渲染组件
 * 根据数据特征自动选择合适的图表类型（折线图、柱状图）
 */
const ChartRenderer: React.FC<ChartRendererProps> = ({ columns, data, title }) => {
  // 转换数据为 Recharts 格式
  const chartData = useMemo(() => {
    return data.map(row => {
      const obj: any = {}
      columns.forEach((col, i) => {
        obj[col] = row[i]
      })
      return obj
    })
  }, [columns, data])

  // 启发式识别图表类型和轴
  const chartConfig = useMemo(() => {
    if (columns.length < 2) return null

    // 找到第一个数值列作为 Y 轴，第一个非数值列（或日期列）作为 X 轴
    let xAxisKey = columns[0]
    let yAxisKey = columns[1]
    let type: 'line' | 'bar' = 'bar'

    // 检查是否有日期相关的列
    const dateColIndex = columns.findIndex(c => 
      c.toLowerCase().includes('date') || 
      c.toLowerCase().includes('time') || 
      c.toLowerCase().includes('日') || 
      c.toLowerCase().includes('月')
    )

    // 检查数值列
    const numericColIndexes = data[0]?.map((_, i) => typeof data[0][i] === 'number') || []
    const firstNumericIndex = numericColIndexes.indexOf(true)

    if (firstNumericIndex !== -1) {
      yAxisKey = columns[firstNumericIndex]
      // 如果有日期列，设为 X 轴并使用折线图
      if (dateColIndex !== -1 && dateColIndex !== firstNumericIndex) {
        xAxisKey = columns[dateColIndex]
        type = 'line'
      } else {
        // 否则找到第一个非数值列作为 X 轴
        const firstNonNumericIndex = numericColIndexes.indexOf(false)
        if (firstNonNumericIndex !== -1) {
          xAxisKey = columns[firstNonNumericIndex]
        }
        type = 'bar'
      }
    }

    return { xAxisKey, yAxisKey, type }
  }, [columns, data])

  if (!chartConfig || data.length === 0) return null

  const { xAxisKey, yAxisKey, type } = chartConfig
  const COLORS = ['#4ca6a8', '#66c2cd', '#85d8ce', '#a3e9df']

  return (
    <div className="w-full h-64 mt-4 mb-2 p-2 bg-white rounded-lg border border-tea/30 shadow-sm">
      {title && <div className="text-xs font-medium text-ink-light mb-2 px-2">{title}</div>}
      <ResponsiveContainer width="100%" height="90%">
        {type === 'line' ? (
          <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey={xAxisKey} 
              fontSize={10} 
              tick={{ fill: '#888' }} 
              axisLine={{ stroke: '#ddd' }}
            />
            <YAxis 
              fontSize={10} 
              tick={{ fill: '#888' }} 
              axisLine={{ stroke: '#ddd' }}
            />
            <Tooltip 
              contentStyle={{ fontSize: '12px', borderRadius: '8px', border: '1px solid #eee' }}
            />
            <Legend wrapperStyle={{ fontSize: '10px' }} />
            <Line 
              type="monotone" 
              dataKey={yAxisKey} 
              stroke="#4ca6a8" 
              strokeWidth={2}
              dot={{ r: 3, fill: '#4ca6a8' }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        ) : (
          <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey={xAxisKey} 
              fontSize={10} 
              tick={{ fill: '#888' }} 
              axisLine={{ stroke: '#ddd' }}
            />
            <YAxis 
              fontSize={10} 
              tick={{ fill: '#888' }} 
              axisLine={{ stroke: '#ddd' }}
            />
            <Tooltip 
              contentStyle={{ fontSize: '12px', borderRadius: '8px', border: '1px solid #eee' }}
            />
            <Legend wrapperStyle={{ fontSize: '10px' }} />
            <Bar dataKey={yAxisKey} fill="#4ca6a8" radius={[4, 4, 0, 0]}>
              {chartData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

export default ChartRenderer
