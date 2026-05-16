package main

import (
	"fmt"
	"html/template"
	"log"
	"net/url"
	"os"
	"strings"
)

func formatPromptText(value interface{}) template.HTML {
	text, ok := value.(string)
	if !ok {
		text = fmt.Sprint(value)
	}
	text = strings.TrimSpace(text)
	if text == "" || text == "<nil>" {
		return ""
	}

	text = strings.ReplaceAll(text, "\r\n", "\n")
	text = strings.ReplaceAll(text, "\r", "\n")

	paragraphs := strings.Split(text, "\n\n")
	var builder strings.Builder
	for _, paragraph := range paragraphs {
		paragraph = strings.Trim(paragraph, "\n")
		if strings.TrimSpace(paragraph) == "" {
			continue
		}
		if builder.Len() > 0 {
			builder.WriteString("\n")
		}
		builder.WriteString("<p>")
		escaped := template.HTMLEscapeString(paragraph)
		builder.WriteString(strings.ReplaceAll(escaped, "\n", "<br>\n"))
		builder.WriteString("</p>")
	}
	return template.HTML(builder.String())
}

func main() {
	fmt.Println("Content-Type: text/html; charset=utf-8")
	fmt.Println()

	config := GetConfig()

	data, err := LoadLemmaData(config.DataFile)
	if err != nil {
		showError(fmt.Sprintf("Failed to load data: %v", err))
		return
	}

	db, err := OpenDatabase(config.DBPath)
	if err != nil {
		showError(fmt.Sprintf("Failed to open database: %v", err))
		return
	}
	defer db.Close()

	params, err := url.ParseQuery(os.Getenv("QUERY_STRING"))
	if err != nil {
		showError(fmt.Sprintf("Failed to parse query: %v", err))
		return
	}

	pageData, err := loadPageData(db, data, params)
	if err != nil {
		showError(err.Error())
		return
	}

	tmpl, err := template.New("translation").Funcs(template.FuncMap{
		"formatPromptText": formatPromptText,
		"siteNav":          siteNavHTML,
	}).Parse(translationReviewTemplate)
	if err != nil {
		showError(fmt.Sprintf("Template error: %v", err))
		return
	}

	if err := tmpl.Execute(os.Stdout, pageData); err != nil {
		log.Printf("Template execution error: %v", err)
	}
}
