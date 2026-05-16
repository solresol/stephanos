package main

import (
	"fmt"
	"html/template"
	"log"
	"net/url"
	"os"
)

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

	tmpl, err := template.New("entities").Funcs(template.FuncMap{
		"siteNav": siteNavHTML,
	}).Parse(entityResolutionTemplate)
	if err != nil {
		showError(fmt.Sprintf("Template error: %v", err))
		return
	}

	if err := tmpl.Execute(os.Stdout, pageData); err != nil {
		log.Printf("Template execution error: %v", err)
	}
}
