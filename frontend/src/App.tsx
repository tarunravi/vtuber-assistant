import './App.css'
import Live2D from './components/Live2D'
import ChatPanel from './components/ChatPanel'
import { appEvents } from './events'

export default function App() {
  return (
    <>
      <Live2D />
      <ChatPanel />
    </>
  )
}
