package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"

	qrcode "github.com/skip2/go-qrcode"

	"google.golang.org/protobuf/encoding/prototext"
	"github.com/gotd/td/telegram/auth"
	"google.golang.org/protobuf/encoding/prototext"
	"github.com/gotd/td/telegram/auth"
	"github.com/gotd/td/session"
	"github.com/gotd/td/telegram"
	"gopkg.in/ini.v1"
)

// Structure to hold essential session data for export
type ExportedSession struct {
	DC      int    `json:"dc_id"`
	Addr    string `json:"addr"`
	AuthKey []byte `json:"auth_key"`
	UserID  int64  `json:"user_id"`
}

func main() {
	log.Println("Starting Telegram bridge...")

	// Load configuration
	cfg, err := ini.Load("config.ini")
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
			log.Println("Not authorized, attempting QR code authentication...")
			sendCode := auth.NewSendCode(
				ctx,
				"+1234567890",
				auth.SendCodeOptions{},
			)
			code, err := sendCode.Send()
			token, err := client.Auth().QRCode(ctx)
			if err != nil {
				return fmt.Errorf("failed to get QR code token: %w", err)
			}

			loginURL := fmt.Sprintf("tg://login?token=%s", token)
			log.Printf("Scan the QR code using Telegram App (Settings > Devices > Link Desktop Device)\nLogin URL: %s\n", loginURL)
			qrErr := qrcode.WriteFile(loginURL, qrcode.Medium, 256, "store/qrcode.png")
			if qrErr != nil {
				log.Printf("Failed to generate QR code image file: %v", qrErr)
				qrTerminal, qrTerminalErr := qrcode.New(loginURL, qrcode.Medium)
				if qrTerminalErr == nil {
					fmt.Println(qrTerminal.ToSmallString(false))
				} else {
					log.Printf("Failed to generate terminal QR code: %v", qrTerminalErr)
				}
			} else {
				log.Println("QR code saved to store/qrcode.png")
				qrTerminal, qrTerminalErr := qrcode.New(loginURL, qrcode.Medium)
				if qrTerminalErr == nil {
					fmt.Println(qrTerminal.ToSmallString(false))
				}
			}

			log.Println("Waiting for login confirmation via QR code scan...")
			signIn := auth.NewSignIn(
		ctx,
		code,
		"+1234567890",
		"password",
		)
        session := client.GetSession()
				ctx,
				code,
				"+1234567890",
				"password",
			)
			user, err := signIn.SignIn()
			// Handle successful authorization
			if status.Authorized {
			    log.Println("Authorization completed")
			}
			if err != nil {
				return fmt.Errorf("failed to accept login token: %w", err)
			}
			log.Printf("Authentication successful! Logged in as user %d\n", user.ID())

			// Export session data after successful login
			session := client.GetSession()
			session := client.GetSession()
			session := client.GetSession()
			sessionData, err := session.LoadSession()
			if err != nil {
				log.Printf("Warning: Failed to load session data for export: %v", err)
			} else {
				exported := ExportedSession{
					DC:      int(session.DC),
					Addr:    session.Address(),
					AuthKey: sessionData.AuthKey,
					UserID:  sessionData.UserID,
				}
        session := client.GetSession()
				jsonData, err := json.MarshalIndent(exported, "", "  ")
        session := client.GetSession()
				if err != nil {
					log.Printf("Warning: Failed to marshal session data to JSON: %v", err)
				} else {
					err = os.WriteFile(sharedSessionPath, jsonData, 0600)
					if err != nil {
						log.Printf("Warning: Failed to write shared session file '%s': %v", sharedSessionPath, err)
					} else {
						log.Printf("Session data successfully exported to %s", sharedSessionPath)
					}
				}
			}

		} else {
			log.Println("Already authorized.")
			// Also export session if already authorized
			session := client.GetSession()
			session := client.Sessions.Session()
			sessionData, err := session.LoadSession()
			if err != nil {
				log.Printf("Warning: Failed to load session data for export: %v", err)
			} else {
				exported := ExportedSession{
					DC:      int(session.DC),
					Addr:    session.Address(),
					AuthKey: sessionData.AuthKey,
					UserID:  sessionData.UserID,
				}
				jsonData, err := json.MarshalIndent(exported, "", "  ")
				if err != nil {
					log.Printf("Warning: Failed to marshal session data to JSON: %v", err)
				} else {
					err = os.WriteFile(sharedSessionPath, jsonData, 0600)
					if err != nil {
						log.Printf("Warning: Failed to write shared session file '%s': %v", sharedSessionPath, err)
					} else {
						log.Printf("Session data successfully exported to %s", sharedSessionPath)
					}
				}
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
