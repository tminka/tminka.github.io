all: papers_by_date.html index.html

# ~/src/python/html_subst/html_subst.py
papers_by_date.html: papers_by_date_template.html papers.db
	python html_subst.py $^ > $@

index.html: papers_by_topic_template.html papers.db
	python html_subst.py $^ > $@
