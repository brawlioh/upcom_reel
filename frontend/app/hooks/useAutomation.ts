'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'
import { useError } from '../contexts/ErrorContext'

interface AutomationJob {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  current_step: number
  total_steps: number
  step_name: string
  created_at: string
  completed_at?: string
  result_path?: string
  online_url?: string  // Added for Creatomate video URLs
  error_message?: string
  request?: AutomationRequest
  game_title?: string  // Game title for display
  steam_app_id?: string  // Steam App ID for reference
}

export type { AutomationJob }

interface AutomationRequest {
  mode: 'single' | 'steam' | 'trending'
  game_title?: string
  steam_app_id?: string
  custom_video_url?: string
  count?: number
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://upcomreel-production.up.railway.app/api'

export function useAutomation() {
  const [currentJob, setCurrentJob] = useState<AutomationJob | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [jobs, setJobs] = useState<AutomationJob[]>([])

  // WebSocket connection with reconnection logic
  const { showError, showWarning } = useError()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 10000 // Increased base delay to 10 seconds
  const lastConnectionAttemptRef = useRef<number>(0) // Track last connection attempt time
  
  const connectWebSocket = useCallback(() => {
    try {
      // Implement connection debouncing - prevent rapid reconnections
      const now = Date.now()
      const timeSinceLastAttempt = now - lastConnectionAttemptRef.current
      
      // Don't allow reconnects more than once every 5 seconds
      if (timeSinceLastAttempt < 5000) {
        console.log(`Debouncing connection attempt. Last attempt was ${timeSinceLastAttempt}ms ago`)
        return
      }
      
      // Update last connection attempt timestamp
      lastConnectionAttemptRef.current = now
      
      // Prevent multiple connection attempts in quick succession
      if (wsRef.current) {
        // If already open, don't reconnect
        if (wsRef.current.readyState === WebSocket.OPEN) {
          console.log('WebSocket already connected, skipping reconnection')
          return // Already connected
        }
        
        // If connecting, don't interrupt
        if (wsRef.current.readyState === WebSocket.CONNECTING) {
          console.log('WebSocket already connecting, skipping reconnection')
          return // Already trying to connect
        }
        
        // Otherwise close the existing connection silently
        try {
          wsRef.current.close(1000, 'Reconnecting')
        } catch (e) {
          // Ignore any close errors
        }
      }
      
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'wss://upcomreel-production.up.railway.app/ws'
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      
      ws.onopen = () => {
        setIsConnected(true)
        console.log('WebSocket connected')
        reconnectAttempts.current = 0 // Reset reconnect counter on successful connection
        
        // Check for active jobs on connection/reconnection
        if (currentJob?.status === 'running' || currentJob?.status === 'queued') {
          fetchJobStatus(currentJob.job_id)
            .then(updatedJob => {
              if (updatedJob.status === 'failed') {
                showError('Automation Failed', updatedJob.error_message || 'The operation failed during processing')
              }
            })
            .catch(err => console.error('Error fetching job status on reconnection:', err))
        }
      }
      
      // Set up ping/pong heartbeat mechanism
      const pingPongEnabled = true
      
      ws.onmessage = (event) => {
        try {
          // First try to parse as JSON
          let data: any
          try {
            data = JSON.parse(event.data)
          } catch (e) {
            // If not JSON, treat as plain text
            if (event.data === 'pong') {
              console.debug('Received pong from server')
              return
            }
            console.debug(`Received non-JSON WebSocket message: ${event.data}`)
            return
          }
          
          // Handle different message types
          switch (data.type) {
            case 'ping':
              // Respond to server pings
              if (ws.readyState === WebSocket.OPEN) {
                ws.send('pong')
              }
              return
              
            case 'connection_established':
              console.log('WebSocket connection established')
              
              // Set up client-side ping/pong
              if (pingPongEnabled && pingIntervalRef.current === null) {
                pingIntervalRef.current = setInterval(() => {
                  if (ws.readyState === WebSocket.OPEN) {
                    ws.send('ping')
                  }
                }, 15000) // Ping every 15 seconds
              }
              return
              
            case 'progress_update':
              // Update current job with progress info
              setCurrentJob(prev => prev ? {
                ...prev,
                current_step: data.step,
                step_name: data.step_name,
                progress: data.progress,
                status: 'running'
              } : null)
              
              // Update jobs list
              setJobs(prev => prev.map(job => 
                job.job_id === data.job_id ? {
                  ...job,
                  current_step: data.step,
                  step_name: data.step_name,
                  progress: data.progress,
                  status: 'running'
                } : job
              ))
              return
              
            case 'job_completed':
              console.log('Job completed:', data.result_path)
              // Update current job with completion data
              setCurrentJob(prev => prev ? {
                ...prev,
                status: 'completed',
                progress: 100,
                current_step: 4,
                step_name: 'Final Compilation',
                result_path: data.result_path,
                online_url: data.result_path, // Assuming result_path is the online URL
                completed_at: new Date().toISOString()
              } : null)
              
              // Update jobs list
              setJobs(prev => prev.map(job => 
                job.job_id === data.job_id ? {
                  ...job,
                  status: 'completed',
                  progress: 100,
                  current_step: 4,
                  step_name: 'Final Compilation',
                  result_path: data.result_path,
                  online_url: data.result_path,
                  completed_at: new Date().toISOString()
                } : job
              ))
              return
              
            case 'job_failed':
              console.error('Job failed:', data.error)
              
              // Only show error modal if it's not related to connections
              const errorMsg = data.error || 'The operation failed during processing'
              if (!errorMsg.toLowerCase().includes('connection') && 
                  !errorMsg.toLowerCase().includes('websocket')) {
                showError('Automation Failed', errorMsg)
              }
              
              // Refresh job status
              fetchJobStatus(data.job_id).catch(err => {
                console.error('Error fetching failed job status:', err)
              })
              return
              
            case 'backend_error':
              // Only show non-connection related errors
              const backendError = data.error || 'An unexpected error occurred in the backend'
              if (!backendError.toLowerCase().includes('connection') && 
                  !backendError.toLowerCase().includes('websocket')) {
                showError('Backend Error', backendError)
              } else {
                console.log(`Suppressed connection error: ${backendError}`)
              }
              return
          }
        } catch (error) {
          // Just log parsing errors, don't show to user
          console.error('Error handling WebSocket message:', error)
        }
      }
      
      ws.onclose = (event) => {
        setIsConnected(false)
        
        // Silently log connection close without showing any UI notification
        console.log(`WebSocket disconnected, code: ${event.code}, reason: ${event.reason}`)
        
        // Clean up ping interval if it exists
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current)
          pingIntervalRef.current = null
        }
        
        // Calculate time since connection was established
        const connectionLifetime = Date.now() - lastConnectionAttemptRef.current
        
        // If the connection was very short-lived (<3 seconds), add extra delay to prevent thrashing
        const wasShortLived = connectionLifetime < 3000
        
        // Only attempt silent reconnection if the close wasn't explicit (code 1000)
        if (reconnectAttempts.current < maxReconnectAttempts && event.code !== 1000) {
          // Increase exponential backoff and add jitter
          // Base delay is longer (10s) and exponent is higher (4 instead of 2)
          const exponent = Math.min(reconnectAttempts.current + 1, 4) // Cap at 4 for sanity
          let delay = reconnectDelay * Math.pow(3, exponent)
          
          // Add jitter to prevent all clients reconnecting simultaneously
          const jitter = Math.floor(Math.random() * 3000)
          delay += jitter
          
          // If connection was short-lived, add extra penalty delay
          if (wasShortLived) {
            delay += 5000
            console.log('Adding penalty delay for short-lived connection')
          }
          
          // Use exponential backoff for reconnection
          console.log(`Scheduling reconnection ${reconnectAttempts.current + 1}/${maxReconnectAttempts} in ${delay/1000}s`)
          
          // Clear any existing reconnect timeout
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
          }
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++
            console.log(`Executing reconnection attempt ${reconnectAttempts.current}/${maxReconnectAttempts}`)
            connectWebSocket()
          }, delay)
        } else {
          if (event.code === 1000) {
            console.log('Not attempting reconnection - clean close')
          } else {
            console.log('Not attempting reconnection - max attempts reached')
          }
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        setIsConnected(false)
      }
    } catch (error) {
      console.error('Error establishing WebSocket connection:', error)
      setIsConnected(false)
      
      // Completely silent - no notifications shown for connection attempts
      // Just continue trying to reconnect in the background
    }
  }, [currentJob, showError])
  
  // Initialize WebSocket connection
  // Store ping interval in a ref so it persists across renders
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  useEffect(() => {
    connectWebSocket()
    
    return () => {
      // Cleanup: close WebSocket and clear all timers
      if (wsRef.current) {
        try {
          // Close with code 1000 means normal closure
          wsRef.current.close(1000, 'Component unmounted')
        } catch (e) {
          console.log('Error closing WebSocket:', e)
        }
        wsRef.current = null
      }
      
      // Clear reconnect timeout if it exists
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      
      // Clear ping interval if it exists
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
        pingIntervalRef.current = null
      }
    }
  }, [connectWebSocket])

  const startAutomation = async (request: AutomationRequest) => {
    // First check health to verify connection
    try {
      console.log('Checking API health before starting automation...')
      const health = await checkHealth()
      if (!health) {
        const errorMessage = `Cannot connect to API server. Make sure the API server is running at ${API_BASE_URL}.`
        console.error(errorMessage)
        showError('Connection Error', errorMessage)
        throw new Error(errorMessage)
      }
      console.log('API health check passed, proceeding with automation')
      
      // API is reachable, now try to start automation
      try {
        console.log(`Sending automation request to ${API_BASE_URL}/automation/start`)
        console.log('Request payload:', request)
        
        const response = await axios.post(`${API_BASE_URL}/automation/start`, request, {
          // Increase timeout for potentially slow operations
          timeout: 10000,
          // Add headers to help with debugging
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          }
        })
        
        console.log('Automation started successfully:', response.data)
        const { job_id } = response.data
        
        // Fetch initial job status
        const jobStatus = await fetchJobStatus(job_id)
        setCurrentJob(jobStatus)
        
        return job_id
      } catch (error) {
        console.error('Error starting automation:', error)
        
        // Extract and show meaningful error message
        let errorMessage = 'Failed to start automation. Please check if the server is running.'
        
        if (axios.isAxiosError(error)) {
          // Handle Axios error responses
          if (error.response) {
            // Server responded with error
            console.error('Server error details:', error.response.data)
            const serverError = error.response.data.detail || error.response.data.message || error.response.data.error
            
            if (serverError) {
              errorMessage = typeof serverError === 'string' ? serverError : JSON.stringify(serverError)
            } else {
              errorMessage = `Server error: ${error.response.status} - ${error.response.statusText}`
            }
          } else if (error.request) {
            // No response received
            errorMessage = `No response from server. Check if the backend is running at ${API_BASE_URL}.`
            console.error('No response received:', error.request)
          } else {
            // Request setup error
            errorMessage = `Error setting up request: ${error.message}`
          }
          
          // Log the config for debugging
          if (error.config) {
            console.error('Request config:', { 
              url: error.config.url,
              method: error.config.method,
              headers: error.config.headers
            })
          }
        } else if (error instanceof Error) {
          errorMessage = error.message
        }
        
        // Show error modal
        showError('Automation Error', errorMessage)
        throw error
      }
    } catch (error) {
      // This catches errors from both the health check and the automation start
      if (!axios.isAxiosError(error)) {
        showError('Connection Error', error instanceof Error ? error.message : 'Unknown error occurred')
      }
      throw error
    }
  }

  const fetchJobStatus = async (jobId: string): Promise<AutomationJob> => {
    try {
      const response = await axios.get(`${API_BASE_URL}/automation/status/${jobId}`)
      return response.data
    } catch (error) {
      console.error('Error fetching job status:', error)
      throw error
    }
  }

  const stopJob = async (jobId: string) => {
    try {
      await axios.delete(`${API_BASE_URL}/automation/stop/${jobId}`)
      setCurrentJob(null)
    } catch (error) {
      console.error('Error stopping job:', error)
      throw error
    }
  }

  const fetchAllJobs = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/automation/jobs`)
      setJobs(response.data)
    } catch (error) {
      console.error('Error fetching jobs:', error)
    }
  }, [])

  const checkHealth = async () => {
    try {
      console.log(`Checking API health at ${API_BASE_URL}/health`)
      const response = await axios.get(`${API_BASE_URL}/health`, {
        // Add timeout to prevent hanging
        timeout: 5000,
        // Explicitly state we're making a CORS request
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
      console.log('API health check successful:', response.data)
      return response.data
    } catch (error) {
      // More verbose error logging
      console.error('Error checking API health:')
      
      if (axios.isAxiosError(error)) {
        if (error.response) {
          console.error(`Status: ${error.response.status}, Data:`, error.response.data)
        } else if (error.request) {
          // The request was made but no response was received
          console.error('No response received from server')
          console.error('Request details:', error.request)
        } else {
          console.error('Error setting up request:', error.message)
        }
        console.error('Error config:', error.config)
      } else {
        console.error('Unexpected error:', error)
      }
      
      return null
    }
  }

  // Fetch jobs on mount
  useEffect(() => {
    fetchAllJobs()
  }, [fetchAllJobs])

  // HTTP polling fallback when WebSocket is disconnected
  // This ensures progress updates even when WebSocket fails
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  
  useEffect(() => {
    // Start polling when there's an active job
    const shouldPoll = currentJob && 
      (currentJob.status === 'running' || currentJob.status === 'queued')
    
    if (shouldPoll) {
      console.log('Starting HTTP polling for job progress (fallback for WebSocket)')
      
      // Poll every 3 seconds for progress updates
      pollingIntervalRef.current = setInterval(async () => {
        try {
          const updatedJob = await fetchJobStatus(currentJob.job_id)
          
          // Update current job with latest status
          setCurrentJob(updatedJob)
          
          // Update jobs list
          setJobs(prev => prev.map(job => 
            job.job_id === updatedJob.job_id ? updatedJob : job
          ))
          
          console.log(`Polling update: Step ${updatedJob.current_step}, Status: ${updatedJob.status}, Progress: ${updatedJob.progress}%`)
          
          // Stop polling if job is completed or failed
          if (updatedJob.status === 'completed' || updatedJob.status === 'failed') {
            console.log(`Job ${updatedJob.status}, stopping polling`)
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current)
              pollingIntervalRef.current = null
            }
          }
        } catch (error) {
          console.error('Polling error:', error)
        }
      }, 3000)
    }
    
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [currentJob?.job_id, currentJob?.status])

  return {
    currentJob,
    jobs,
    isConnected,
    startAutomation,
    stopJob,
    fetchJobStatus,
    fetchAllJobs,
    checkHealth
  }
}
