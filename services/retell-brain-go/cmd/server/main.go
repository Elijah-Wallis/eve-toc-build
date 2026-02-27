package main

import (
	"context"
	"log"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/gorilla/websocket"

	"eve-toc-build/services/retell-brain-go/internal/protocol"
)

type incomingEvent struct {
	InteractionType string `json:"interaction_type"`
	ResponseID      string `json:"response_id"`
	AutoReconnect   bool   `json:"auto_reconnect"`
}

type outgoingEvent struct {
	InteractionType string `json:"interaction_type,omitempty"`
	ResponseID      string `json:"response_id,omitempty"`
	Content         string `json:"content,omitempty"`
	ContentComplete bool   `json:"content_complete,omitempty"`
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type session struct {
	conn *websocket.Conn

	mu           sync.Mutex
	state        protocol.State
	currentCancel context.CancelFunc

	writeMu  sync.Mutex
	closeOnce sync.Once
	closed    atomic.Bool
}

func main() {
	http.HandleFunc("/ws/", handleWS)
	addr := ":8099"
	log.Printf("retell-brain-go listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, nil))
}

func handleWS(w http.ResponseWriter, r *http.Request) {
	_, callID := splitCallID(r.URL.Path)
	if callID == "" {
		http.Error(w, "missing call_id", http.StatusBadRequest)
		return
	}
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}

	s := &session{
		conn: conn,
		state: protocol.State{
			OutboundStreamingOpen: true,
		},
	}
	defer s.close()

	go s.keepaliveLoop()
	go s.watchdogLoop()

	for {
		var evt incomingEvent
		if err := conn.ReadJSON(&evt); err != nil {
			return
		}
		if err := s.onEvent(evt); err != nil {
			return
		}
	}
}

func (s *session) onEvent(evt incomingEvent) error {
	now := time.Now().UTC()

	s.mu.Lock()
	if evt.AutoReconnect && !s.state.AutoReconnect {
		s.state.AutoReconnect = true
		if s.state.LastPingPongAt.IsZero() {
			s.state.LastPingPongAt = now
		}
	}

	decision := s.state.HandleInteraction(evt.InteractionType, evt.ResponseID, now)
	if decision.CancelGeneration {
		s.cancelGenerationLocked()
	}
	if decision.StartNewGeneration {
		s.startGenerationLocked(evt.ResponseID)
	}
	s.mu.Unlock()

	if decision.SendPingPong {
		if err := s.writeJSON(outgoingEvent{InteractionType: "ping_pong"}); err != nil {
			return err
		}
	}
	return nil
}

func (s *session) startGenerationLocked(responseID string) {
	if responseID == "" {
		responseID = "response-default"
	}
	if s.currentCancel != nil {
		s.currentCancel()
		s.currentCancel = nil
	}
	ctx, cancel := context.WithCancel(context.Background())
	s.currentCancel = cancel
	go s.streamDeterministic(ctx, responseID)
}

func (s *session) cancelGenerationLocked() {
	if s.currentCancel != nil {
		s.currentCancel()
		s.currentCancel = nil
	}
}

func (s *session) streamDeterministic(ctx context.Context, responseID string) {
	chunks := []string{"deterministic-chunk-1", "deterministic-chunk-2", "deterministic-chunk-3"}
	for idx, content := range chunks {
		select {
		case <-ctx.Done():
			return
		default:
		}
		time.Sleep(120 * time.Millisecond)

		s.mu.Lock()
		active := s.state.GenerationActive && s.state.CurrentResponseID == responseID
		outbound := s.state.OutboundStreamingOpen
		s.mu.Unlock()
		if !active {
			return
		}
		if !outbound {
			continue
		}

		evt := outgoingEvent{
			ResponseID: responseID,
			Content:    content,
		}
		if idx == len(chunks)-1 {
			evt.ContentComplete = true
		}
		if err := s.writeJSON(evt); err != nil {
			s.close()
			return
		}
	}

	s.mu.Lock()
	if s.state.CurrentResponseID == responseID {
		s.state.GenerationActive = false
	}
	s.mu.Unlock()
}

func (s *session) keepaliveLoop() {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		if s.closed.Load() {
			return
		}
		s.mu.Lock()
		autoReconnect := s.state.AutoReconnect
		s.mu.Unlock()
		if !autoReconnect {
			continue
		}
		if err := s.writeJSON(outgoingEvent{InteractionType: "ping_pong"}); err != nil {
			s.close()
			return
		}
	}
}

func (s *session) watchdogLoop() {
	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()
	for range ticker.C {
		if s.closed.Load() {
			return
		}
		s.mu.Lock()
		stale := s.state.HeartbeatStale(time.Now().UTC())
		s.mu.Unlock()
		if stale {
			s.close()
			return
		}
	}
}

func (s *session) writeJSON(payload outgoingEvent) error {
	s.writeMu.Lock()
	defer s.writeMu.Unlock()
	return s.conn.WriteJSON(payload)
}

func (s *session) close() {
	s.closeOnce.Do(func() {
		s.closed.Store(true)
		s.mu.Lock()
		if s.currentCancel != nil {
			s.currentCancel()
			s.currentCancel = nil
		}
		s.mu.Unlock()
		_ = s.conn.Close()
	})
}

func splitCallID(path string) (string, string) {
	trimmed := strings.Trim(path, "/")
	parts := strings.Split(trimmed, "/")
	if len(parts) < 2 {
		return "", ""
	}
	return parts[0], parts[1]
}
