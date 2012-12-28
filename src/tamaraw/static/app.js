$(function () {

"use strict";

_.mixin({
	partition: function (arr, size){
		if (_.size(arr) <= size) {
			return [arr];
	    }
	    return [_.first(arr, size)].concat(_.partition(_.rest(arr,size), size));
	}
});
	
window.Image = Backbone.Model.extend();

window.ImageCollection = Backbone.Paginator.requestPager.extend({
	model: Image,
	paginator_core: {
		url: '/api/images',
		dataType: 'json'
	},
	paginator_ui: {
		firstPage: 0,
		currentPage: 0,
		perPage: 8,
		totalPages: 2342
	},
	server_api:{
		'length': function() { return this.perPage; },
		'offset': function() { return this.currentPage * this.perPage; }
	},
	parse: function(obj) {
		this.totalPages = Math.ceil(obj.total / this.perPage);
		this.totalRecords = obj.total;
		return obj.images;
	}
});

window.ImageListView = Backbone.View.extend({
	tagName: 'div',
	initialize: function() {
		this.model.bind("reset", this.render, this);
	},
	events:{
		'click a.servernext': 'nextPage',
		'click a.serverprevious': 'previousPage'
	},
	nextPage: function(e) {
		e.preventDefault();
		app.navigate("images/" + (this.model.currentPage + 1));
		this.model.goTo(this.model.currentPage + 1);
	},
	previousPage: function(e) {
		e.preventDefault();
		app.navigate("images/" + (this.model.currentPage - 1));
		this.model.goTo(this.model.currentPage - 1);
	},
	pagerTemplate: _.template($('#tpl-pager').html()),
	render: function(eventName) {
		this.$el.html('');
		_.each(_.partition(this.model.models, 4), function(images) {
			var listElement = $('<ul class="thumbnails"></ul>').appendTo(this.$el)
			_.each(images, function(image) {
				listElement.append(new ImageListItemView({model: image }).render().el);
			}, this);
		}, this);
		this.$el.append(this.pagerTemplate(this.model));
		return this;
	}
});

window.ImageListItemView = Backbone.View.extend({
	tagName: 'li',
	className: 'span3',
	initialize: function(){
		this.model.bind("reset", this.render, this);
	},
	template: _.template($('#tpl-image-list-item').html()),
	render: function(eventName) {
		this.$el.html(this.template(this.model.toJSON()));
		return this;
	}
});

var AppRouter = Backbone.Router.extend({
	routes: {
		"images/:page": "list"
	},
	imageList: null,
	imageListView: null,
	list: function(page) {
		
		if (this.imageList == null) {
			this.imageList = new ImageCollection();
			this.imageListView = new ImageListView({model: this.imageList})
		}
		this.imageList.goTo(page);
		$('#content').html(this.imageListView.render().el);
	}
});

window.app = new AppRouter();
Backbone.history.start({pushState: true, root: "/app/"});
app.navigate("images/0", {trigger: true, replace: true});
});
