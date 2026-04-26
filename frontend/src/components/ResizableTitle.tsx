import type { SyntheticEvent } from 'react'
import { Resizable, type ResizeCallbackData } from 'react-resizable'

interface ResizableTitleProps {
  onResize: (e: SyntheticEvent, data: ResizeCallbackData) => void
  width: number
  minWidth?: number
  [key: string]: unknown
}

function ResizableTitle({ onResize, width, minWidth = 60, ...restProps }: ResizableTitleProps) {
  if (!width) {
    return <th {...restProps} />
  }

  return (
    <Resizable
      width={width}
      height={0}
      minConstraints={[minWidth, 0]}
      handle={
        <span
          className="react-resizable-handle"
          onClick={(e) => e.stopPropagation()}
        />
      }
      onResize={onResize}
      draggableOpts={{ enableUserSelectHack: false }}
    >
      <th {...restProps} />
    </Resizable>
  )
}

export default ResizableTitle
