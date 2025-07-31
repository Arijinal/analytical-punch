import { useEffect, useRef, useCallback } from 'react';
import useWebSocketLib from 'react-use-websocket';
import { useChartStore } from '../store/chartStore';
import toast from 'react-hot-toast';

const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

const useWebSocket = () => {
  const subscriptionsRef = useRef(new Set());
  const {
    selectedSymbol,
    selectedTimeframe,
    updatePrice,
    updateIndicator,
    addSignal
  } = useChartStore();

  const {
    sendMessage,
    lastMessage,
    readyState,
    getWebSocket
  } = useWebSocketLib(WS_URL, {
    onOpen: () => {
      console.log('WebSocket connected');
      toast.success('Real-time updates connected', { duration: 2000 });
      
      // Resubscribe to previous subscriptions
      subscriptionsRef.current.forEach(sub => {
        const [symbol, interval] = sub.split(':');
        subscribe(symbol, interval);
      });
    },
    onClose: () => {
      console.log('WebSocket disconnected');
    },
    onError: (error) => {
      console.error('WebSocket error:', error);
      toast.error('Real-time connection error', { duration: 3000 });
    },
    shouldReconnect: () => true,
    reconnectInterval: 3000,
    reconnectAttempts: 10,
  });

  // Subscribe to symbol updates
  const subscribe = useCallback((symbol, interval) => {
    if (readyState === WebSocket.OPEN) {
      sendMessage(JSON.stringify({
        type: 'subscribe',
        symbol,
        interval
      }));
      subscriptionsRef.current.add(`${symbol}:${interval}`);
    }
  }, [readyState, sendMessage]);

  // Unsubscribe from symbol updates
  const unsubscribe = useCallback((symbol) => {
    if (readyState === WebSocket.OPEN) {
      sendMessage(JSON.stringify({
        type: 'unsubscribe',
        symbol
      }));
      
      // Remove all subscriptions for this symbol
      subscriptionsRef.current.forEach(sub => {
        if (sub.startsWith(`${symbol}:`)) {
          subscriptionsRef.current.delete(sub);
        }
      });
    }
  }, [readyState, sendMessage]);

  // Handle incoming messages
  useEffect(() => {
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage.data);
        
        switch (data.type) {
          case 'price_update':
            updatePrice(data.symbol, data.data);
            break;
            
          case 'indicator_update':
            updateIndicator(data.symbol, data.indicator, data.data);
            break;
            
          case 'signal':
            addSignal(data.symbol, data.signal);
            break;
            
          case 'subscribed':
            console.log(`Subscribed to ${data.symbol} ${data.interval}`);
            break;
            
          case 'unsubscribed':
            console.log(`Unsubscribed from ${data.symbol}`);
            break;
            
          case 'pong':
            // Heartbeat response
            break;
            
          default:
            console.log('Unknown message type:', data.type);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    }
  }, [lastMessage, updatePrice, updateIndicator, addSignal]);

  // Subscribe to current symbol/timeframe
  useEffect(() => {
    if (selectedSymbol && selectedTimeframe && readyState === WebSocket.OPEN) {
      // Unsubscribe from all first
      subscriptionsRef.current.forEach(sub => {
        const [symbol] = sub.split(':');
        unsubscribe(symbol);
      });
      
      // Subscribe to new symbol/timeframe
      subscribe(selectedSymbol, selectedTimeframe);
    }
  }, [selectedSymbol, selectedTimeframe, readyState, subscribe, unsubscribe]);

  // Heartbeat to keep connection alive
  useEffect(() => {
    const interval = setInterval(() => {
      if (readyState === WebSocket.OPEN) {
        sendMessage(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // Every 30 seconds

    return () => clearInterval(interval);
  }, [readyState, sendMessage]);

  return {
    isConnected: readyState === WebSocket.OPEN,
    subscribe,
    unsubscribe,
    sendMessage: (data) => {
      if (readyState === WebSocket.OPEN) {
        sendMessage(JSON.stringify(data));
      }
    }
  };
};

export default useWebSocket;