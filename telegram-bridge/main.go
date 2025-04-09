package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"time"

	"github.com/gotd/td/session"
	"github.com/gotd/td/telegram"
	"github.com/skip2/go-qrcode"
	"gopkg.in/ini.v1"
)

// Structure to hold essential session data for export
type ExportedSession struct {
	DC      int    `json:"dc_id"`
	Addr    string `json:"addr"`
	AuthKey []byte `json:"auth_key"`
	UserID  int64  `json:"user_id"`
}

// Data structure that should match the gotd/td session format
type SessionData struct {
	DC      int    `json:"dc_id"`
	Addr    string `json:"addr"`
	AuthKey []byte `json:"auth_key"`
	UserID  int64  `json:"user_id"`
}

func main() {
	log.Println("Starting Telegram bridge...")

	// Load configuration
	cfg, err := ini.Load("telegram-bridge/config.ini")
	if err != nil {
		log.Fatalf("Failed to load config: %v\n", err)
	}

	apiIDStr := cfg.Section("telegram").Key("api_id").String()
	apiHash := cfg.Section("telegram").Key("api_hash").String()

	var apiID int
	_, err = fmt.Sscan(apiIDStr, &apiID)
	if err != nil {
		log.Fatalf("Invalid api_id: %v\n", err)
	}

	if apiHash == "" || apiID == 0 {
		log.Fatalf("api_id and api_hash must be set in config.ini")
	}

	// Set up session storage
	sessionDir := "store"
	if err := os.MkdirAll(sessionDir, 0700); err != nil {
		log.Fatalf("Failed to create session directory: %v", err)
	}
	sessionStorage := &session.FileStorage{
		Path: fmt.Sprintf("%s/telegram.session", sessionDir),
	}
	sessionFilePath := fmt.Sprintf("%s/telegram.session", sessionDir)
	sharedSessionPath := fmt.Sprintf("%s/shared_session.json", sessionDir) // Path for JSON export

	// Create Telegram client
	client := telegram.NewClient(apiID, apiHash, telegram.Options{
		SessionStorage: sessionStorage,
	})

	// Run the client
	err = client.Run(context.Background(), func(ctx context.Context) error {
		log.Println("Client started, checking authentication...")

		status, err := client.Auth().Status(ctx)
		if err != nil {
			return fmt.Errorf("failed to get auth status: %w", err)
		}

		if !status.Authorized {
			log.Println("Not authorized. Please scan the QR code below with Telegram mobile app.")
			log.Println("Open Telegram app → Settings → Devices → Link Desktop Device")

			// Generate QR code for web.telegram.org
			loginURL := "https://web.telegram.org/a/"
			if err := qrcode.WriteFile(loginURL, qrcode.Medium, 256, "store/qrcode.png"); err != nil {
				log.Printf("Failed to generate QR code image: %v", err)
			} else {
				log.Println("QR code saved to store/qrcode.png")
			}

			// Also show terminal QR code
			qrTerminal, err := qrcode.New(loginURL, qrcode.Medium)
			if err == nil {
				fmt.Println(qrTerminal.ToSmallString(false))
			}

			// Wait for user to scan QR code and login
			log.Println("Waiting for authorization... Please scan the QR code.")
			for {
				// Check every few seconds if we're authorized
				time.Sleep(3 * time.Second)

				status, err := client.Auth().Status(ctx)
				if err != nil {
					log.Printf("Error checking auth status: %v", err)
					continue
				}

				if status.Authorized {
					log.Println("Authorization successful!")
					break
				}
			}

			// Export session data after successful login
			if err := exportSession(sessionFilePath, sharedSessionPath); err != nil {
				log.Printf("Warning: Failed to export session: %v", err)
			}
		} else {
			log.Println("Already authorized.")
			// Also export session if already authorized
			if err := exportSession(sessionFilePath, sharedSessionPath); err != nil {
				log.Printf("Warning: Failed to export session: %v", err)
			}
		}

		self, err := client.Self(ctx)
		if err != nil {
			return fmt.Errorf("failed to get self info: %w", err)
		}
		log.Printf("Logged in as: %s %s (@%s)\n", self.FirstName, self.LastName, self.Username)

		log.Println("Telegram bridge running. Press Ctrl+C to exit.")
		<-ctx.Done()
		return ctx.Err()
	})

	if err != nil {
		log.Fatalf("Telegram client run failed: %v", err)
	}

	log.Println("Telegram bridge stopped.")
}

// exportSession reads the session file directly and exports it to the specified path
func exportSession(sessionFilePath, exportPath string) error {
	// Read the session file
	sessionFileData, err := ioutil.ReadFile(sessionFilePath)
	if err != nil {
		return fmt.Errorf("failed to read session file: %w", err)
	}

	// Try to parse the session data
	var sessionData SessionData
	if err := json.Unmarshal(sessionFileData, &sessionData); err != nil {
		return fmt.Errorf("failed to parse session data: %w", err)
	}

	// Create exported session data
	exported := ExportedSession{
		DC:      sessionData.DC,
		Addr:    sessionData.Addr,
		AuthKey: sessionData.AuthKey,
		UserID:  sessionData.UserID,
	}

	// Export to the shared session file
	jsonData, err := json.MarshalIndent(exported, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal session data to JSON: %w", err)
	}

	err = os.WriteFile(exportPath, jsonData, 0600)
	if err != nil {
		return fmt.Errorf("failed to write shared session file '%s': %w", exportPath, err)
	}

	log.Printf("Session data successfully exported to %s", exportPath)
	return nil
}
