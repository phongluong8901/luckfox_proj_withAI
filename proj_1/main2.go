package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	ledTrigger    = "/sys/class/leds/work/trigger"
	ledBrightness = "/sys/class/leds/work/brightness"
	cpuTempPath   = "/sys/class/thermal/thermal_zone0/temp"
)

func readCPUTemp() float64 {
	data, err := os.ReadFile(cpuTempPath)
	if err != nil {
		return 0.0
	}
	raw, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil {
		return 0.0
	}
	return float64(raw) / 1000.0
}

func main() {
	fmt.Println("=== Bat dau dieu khien phan cung Luckfox Pico Zero ===")

	// 1. Tắt chế độ nháy tự động để tự điều khiển bằng code
	_ = os.WriteFile(ledTrigger, []byte("none"), 0644)

	// 2. Cho LED nhấp nháy 5 lần với độ sáng tối đa (255)
	for i := 1; i <= 5; i++ {
		temp := readCPUTemp()

		// Bật LED sáng tối đa (255)
		_ = os.WriteFile(ledBrightness, []byte("255"), 0644)
		fmt.Printf("[Chu ky %d] LED: ON  | Nhiet do SoC RV1106: %.2f °C\n", i, temp)
		time.Sleep(500 * time.Millisecond)

		// Tắt LED (0)
		_ = os.WriteFile(ledBrightness, []byte("0"), 0644)
		fmt.Printf("[Chu ky %d] LED: OFF | Nhiet do SoC RV1106: %.2f °C\n", i, temp)
		time.Sleep(500 * time.Millisecond)
	}

	// 3. Trả lại đúng chế độ "activity" mặc định của Luckfox Pico Zero
	_ = os.WriteFile(ledTrigger, []byte("activity"), 0644)
	fmt.Println("=== Hoan thanh! Da tra LED ve che do activity ===")
}