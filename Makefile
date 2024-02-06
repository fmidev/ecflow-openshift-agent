PROG = ecflow-openshift-agent

rpmsourcedir = /tmp/$(shell whoami)/rpmbuild

ifeq ($(VERSION),)
  VERSION=$(shell date -u +%y).$(shell date -u +%m | sed 's/^0*//').$(shell date -u +%d | sed 's/^0*//')
endif

ifeq ($(RELEASE),)
  RELEASE=$(shell date -u +%H%M).$(shell git rev-parse --short HEAD)
endif

# The rules

rpm:	
	mkdir -p $(rpmsourcedir) ; \
        tar -C ../ --exclude-vcs \
                 -cf $(rpmsourcedir)/python3-$(PROG).tar $(PROG) ; \
        gzip -f $(rpmsourcedir)/python3-$(PROG).tar ; \
        rpmbuild -ta --define="version $(VERSION)" --define="release $(RELEASE)" $(rpmsourcedir)/python3-$(PROG).tar.gz ; \
        rm -f $(rpmsourcedir)/*$(PROG).tar.gz ; 
